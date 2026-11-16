"""MOD-3B: real-mail proof for the membership broadcast footer and the payment dunning recipients.

Everything runs through the real outbox, the real EmailLog and the locmem backend; only the broker
enqueue is a no-op. Assertions name the exact URL shape, token contents, recipient and tenant.
"""
from urllib.parse import quote, urlsplit

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.integrations.dispatch import _deliver
from apps.integrations.email_preferences import decode_unsubscribe
from apps.integrations.models import EmailLog, NotificationPreference
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_tasks import deliver_envelope
from apps.notifications.models import MemberNotificationPreference
from apps.payments.notifications import notify_payment
from tests.notifications.test_broadcasts import url, world
from tests.return_helpers import authenticated_client, make_member
from tests.test_notification_families_f3 import family_world

pytestmark = pytest.mark.django_db
BASE = "https://makers.example"


@pytest.fixture(autouse=True)
def _locmem(settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PUBLIC_APP_BASE_URL = BASE
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda pk: None)
    mail.outbox.clear()


def _send_queued(space):
    for envelope in NotificationEnvelope.objects.filter(makerspace=space).order_by("pk"):
        deliver_envelope(envelope.pk)
    for log in EmailLog.objects.filter(makerspace=space, status="queued").order_by("pk"):
        _deliver(log)


def test_membership_broadcast_mail_carries_a_tenant_scoped_working_unsubscribe(django_capture_on_commit_callbacks):
    space, manager, member = world("mod3b-bcast")
    other_space, _m, _o = world("mod3b-bcast-other")
    with django_capture_on_commit_callbacks(execute=True):
        created = authenticated_client(manager).post(url(space), {"title": "Room change", "body": "Annex."}, format="json")
    assert created.status_code == 201
    _send_queued(space)
    sent = [m for m in mail.outbox if m.to == [member.email]]
    assert len(sent) == 1
    message = sent[0]
    marker = f"Unsubscribe from these emails: {BASE}/unsubscribe/"
    assert marker in message.body
    token_part = message.body.split(marker)[1].split()[0]
    from urllib.parse import unquote
    token = unquote(token_part)
    assert f"{BASE}/unsubscribe/{quote(token, safe='')}" in message.body
    claims = decode_unsubscribe(token)
    assert claims == {"space": space.pk, "user": member.pk, "feature": "members"}
    assert claims["space"] != other_space.pk
    header = message.extra_headers["List-Unsubscribe"]
    assert header.startswith(f"<{BASE}/api/v1/notifications/unsubscribe/") and header.endswith(f"{token}>")
    assert message.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    path = urlsplit(header.strip("<>")).path
    client = APIClient()
    assert client.get(path).status_code == 302
    assert not MemberNotificationPreference.objects.filter(user=member).exists()
    response = client.post(path, "List-Unsubscribe=One-Click", content_type="application/x-www-form-urlencoded")
    assert response.status_code == 200
    assert MemberNotificationPreference.objects.filter(
        makerspace=space, user=member, feature="members", channel="email", enabled=False).count() == 1
    assert not MemberNotificationPreference.objects.filter(makerspace=other_space).exists()


@pytest.mark.parametrize("event", ["payment_due_soon", "payment_due_today", "payment_overdue"])
def test_payment_dunning_mail_goes_only_to_the_payer_and_carries_no_foreign_data(event):
    space, manager, member, payment = family_world("mod3b-dun-a")
    other_space, _om, other_member, other_payment = family_world("mod3b-dun-b")
    for target in (space, other_space):
        target.enabled_modules = sorted(set(target.enabled_modules) | {"email", "notifications"})
        target.save(update_fields=["enabled_modules", "updated_at"])
        NotificationPreference.objects.create(makerspace=target, feature="payments", channel="email", enabled=True)
    other_payment.amount = "1357.91"
    other_payment.save(update_fields=["amount"])
    bystander = make_member("mod3b-dun-bystander", space)
    notify_payment(payment, event, requester_only=True)
    notify_payment(other_payment, event, requester_only=True)
    _send_queued(space)
    _send_queued(other_space)
    own = EmailLog.objects.filter(makerspace=space, event=event)
    assert [log.to_email for log in own] == [member.email]
    assert own.get().recipient_id == member.pk
    assert not EmailLog.objects.filter(makerspace=space, to_email__in=[manager.email, bystander.email]).exists()
    foreign = EmailLog.objects.filter(makerspace=other_space, event=event)
    assert [log.to_email for log in foreign] == [other_member.email]
    to_own = [m for m in mail.outbox if m.to == [member.email]]
    assert len(to_own) == 1
    text = to_own[0].body + "".join(a[0] for a in getattr(to_own[0], "alternatives", []))
    assert space.name in text and other_space.name not in text
    assert "1357.91" not in text and other_member.email not in text
    assert all(m.to in ([member.email], [other_member.email]) for m in mail.outbox)
