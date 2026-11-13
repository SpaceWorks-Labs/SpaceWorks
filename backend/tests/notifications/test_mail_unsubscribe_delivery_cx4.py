"""The URL mailed to a member works, and owner-only debt mail stays tenant-scoped."""
from urllib.parse import quote, unquote

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.integrations.email_preferences import decode_unsubscribe
from apps.integrations.dispatch import _deliver
from apps.integrations.models import EmailLog, NotificationPreference
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.notification_tasks import deliver_envelope
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.notifications.models import MemberNotificationPreference
from apps.payments.notifications import notify_payment
from tests.notifications.test_broadcasts import url, world
from tests.return_helpers import authenticated_client
from tests.test_notification_families_f3 import family_world

pytestmark = pytest.mark.django_db
BASE = "https://makers.example"


def _send_queued(space):
    for envelope in NotificationEnvelope.objects.filter(makerspace=space).order_by("pk"):
        deliver_envelope(envelope.pk)
    for log in EmailLog.objects.filter(makerspace=space, status="pending").order_by("pk"):
        _deliver(log)


@pytest.fixture(autouse=True)
def mail_only(settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PUBLIC_APP_BASE_URL = BASE
    settings.NOTIFICATION_FANOUT_VIA_CELERY = False
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)
    monkeypatch.setattr("apps.integrations.dispatch_outbox._enqueue", lambda *_: None)
    mail.get_connection()  # initializes locmem outbox even when this file is selected alone
    mail.outbox.clear()


def test_broadcast_unsubscribe_link_redirects_to_the_exact_confirm_url_and_is_tenant_local(
        django_capture_on_commit_callbacks):
    space, manager, member = world("cx4-unsubscribe")
    other, _, _ = world("cx4-unsubscribe-other")
    # One person belongs to two spaces: the capability must affect just its signed tenant.
    from tests.accounts.account_factories import make_membership
    make_membership(member, other)
    MemberNotificationPreference.objects.create(makerspace=other, user=member,
        feature="members", channel="email", enabled=True)
    with django_capture_on_commit_callbacks(execute=True):
        response = authenticated_client(manager).post(url(space), {"title": "Build night", "body": "Annex"}, format="json")
    assert response.status_code == 201
    _send_queued(space)
    [message] = [message for message in mail.outbox if message.to == [member.email]]
    prefix = f"Unsubscribe from these emails: {BASE}/unsubscribe/"
    token = unquote(message.body.split(prefix, 1)[1].split()[0])
    assert f"{BASE}/unsubscribe/{quote(token, safe='')}" in message.body
    assert decode_unsubscribe(token) == {"space": space.pk, "user": member.pk, "feature": "members"}
    header = message.extra_headers["List-Unsubscribe"]
    api_token = header.removeprefix(f"<{BASE}/api/v1/notifications/unsubscribe/").removesuffix(">")
    assert decode_unsubscribe(api_token) == decode_unsubscribe(token)
    api_path = f"/api/v1/notifications/unsubscribe/{api_token}"
    assert message.extra_headers == {
        "List-Unsubscribe": f"<{BASE}{api_path}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    client = APIClient()
    landing = client.get(api_path)
    assert landing.status_code == 302
    assert landing["Location"] == f"{BASE}/unsubscribe/{quote(api_token, safe='')}"
    assert MemberNotificationPreference.objects.filter(makerspace=space, user=member).count() == 0
    for _ in range(2):
        response = client.post(api_path, {"List-Unsubscribe": "One-Click"}, format="json")
        assert response.status_code == 200
    assert list(MemberNotificationPreference.objects.filter(user=member).order_by("makerspace_id")
                .values_list("makerspace_id", "feature", "channel", "enabled")) == sorted([
                    (space.pk, "members", "email", False), (other.pk, "members", "email", True)])


@pytest.mark.parametrize("event", ["payment_due_soon", "payment_due_today", "payment_overdue"])
def test_debt_mail_is_owner_only_without_the_requester_only_hint_and_replay_sends_nothing(event):
    space, manager, member, payment = family_world("cx4-debt-cedar")
    other, other_manager, other_member, foreign_payment = family_world("cx4-debt-maple")
    for tenant in (space, other):
        install_module(tenant, "email")
        install_module(tenant, "notifications")
        uninstall_module(tenant, "payments")
        NotificationPreference.objects.create(makerspace=tenant, feature="payments", channel="email", enabled=True)
    # Distinct tenant text and amounts make a template/context mix-up observable.
    foreign_payment.amount = "1357.91"
    foreign_payment.save(update_fields=["amount"])
    for charge in (payment, foreign_payment):
        notify_payment(charge, event)  # the event itself MUST narrow to the owner
        _send_queued(charge.makerspace)
        notify_payment(charge, event)
        _send_queued(charge.makerspace)
    assert sorted(message.to for message in mail.outbox) == sorted([[member.email], [other_member.email]])
    assert list(EmailLog.objects.filter(event=event).order_by("makerspace_id")
                .values_list("makerspace_id", "recipient_id", "to_email", "status")) == sorted([
                    (space.pk, member.pk, member.email, "sent"),
                    (other.pk, other_member.pk, other_member.email, "sent")])
    assert not EmailLog.objects.filter(to_email__in=[manager.email, other_manager.email]).exists()
    for recipient, tenant, foreign_tenant, forbidden_amount in (
            (member, space, other, "1357.91"), (other_member, other, space, "9876.54")):
        [message] = [message for message in mail.outbox if message.to == [recipient.email]]
        body = message.body + "".join(alternative[0] for alternative in message.alternatives)
        assert tenant.name in body
        assert foreign_tenant.name not in body
        assert forbidden_amount not in body
