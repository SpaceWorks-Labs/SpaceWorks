"""Departure keeps its low-level audited seam; reminders retain live identity gates."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.account_deletion_presence import end_owned_presence
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import MakerspaceMembership
from apps.presence.models import PresenceSession
from apps.presence.notifications import eligible, remind
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def setup_session():
    space = make_space("recon-presence")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"presence"})
    space.save(update_fields=["enabled_modules"])
    user = make_user("recon-presence-owner", access_status="active")
    now = timezone.now()
    row = PresenceSession.objects.create(makerspace=space, member=user, account=user,
        status="guest", hide_on_display=True, started_at=now - timedelta(hours=1),
        expires_at=now - timedelta(seconds=1), ended_at=now, end_reason="expired")
    return space, user, row


def test_expiry_is_revision_bound_private_and_independent_of_membership(monkeypatch):
    space, user, row = setup_session()
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    envelope = remind(row)
    assert eligible(envelope)
    assert envelope.context == {} and "coordinates" not in envelope.message_body
    assert user.email not in envelope.message_body
    row.revision += 1
    row.save(update_fields=["revision"])
    assert not eligible(envelope)


@pytest.mark.parametrize("state", ["revoked", "deleted", "module_off"])
def test_expiry_rechecks_standing_and_module(monkeypatch, state):
    space, user, row = setup_session()
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    envelope = remind(row)
    if state == "revoked":
        MakerspaceMembership.objects.create(user=user, makerspace=space, role="custom", status="revoked",
                                             assigned_role=space.roles.get(slug="member"))
    elif state == "deleted":
        User.objects.filter(pk=user.pk).update(deletion_requested_at=timezone.now(), is_active=False)
        envelope.recipient.refresh_from_db()
    else:
        space.enabled_modules.remove("presence")
        space.save(update_fields=["enabled_modules"])
        envelope.makerspace.refresh_from_db()
    assert not eligible(envelope)


def test_account_only_departure_ends_owned_sessions_with_module_off():
    space, user, row = setup_session()
    row.ended_at, row.end_reason = None, ""
    row.save(update_fields=["ended_at", "end_reason"])
    space.enabled_modules.remove("presence")
    space.save(update_fields=["enabled_modules"])
    other = make_user("recon-presence-other", access_status="active")
    outsider = PresenceSession.objects.create(makerspace=space, account=other, member=other,
        started_at=timezone.now() - timedelta(minutes=1), expires_at=timezone.now() + timedelta(hours=1))
    now = timezone.now()
    end_owned_presence(user, [space], now)
    row.refresh_from_db()
    outsider.refresh_from_db()
    assert row.ended_at == now and row.ended_by_id == user.pk and row.end_reason == "user_ended"
    assert outsider.ended_at is None
    log = AuditLog.objects.get(action="presence.ended", target_id=str(row.pk))
    assert log.actor_id == user.pk and log.meta == {"reason": "user_ended"}
