from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.events.invites import create_invite, redeem_invite, resolve_for_account
from apps.events.services_bulk_invites import bulk_invites
from apps.events.services_registration import register
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.delivery_content import content
from apps.integrations.models import EmailLog
from tests.events.lane_d_helpers import fixture, smtp
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db


def test_bulk_code_free_email_and_code_free_admission(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    newcomer = account("invited"); newcomer.email_verified_at = timezone.now(); newcomer.save()
    event.registration_audience = "invite"; event.save()
    assert bulk_invites(event, actor, [newcomer.email, newcomer.email.upper()]) == 1
    log = EmailLog.objects.get(source_kind="event_invitation")
    invite = event.invites.get()
    assert log.source_id == invite.pk and not log.text_body
    send = smtp(monkeypatch); _deliver(log)
    assert send.called and "You're invited" in content(log).text_body
    assert "invite_code" not in content(log).text_body and invite.code_digest not in content(log).text_body
    row = register(event, member=newcomer, actor=newcomer)
    invite.refresh_from_db(); assert row.invite_id == invite.pk and invite.uses == 1
    assert resolve_for_account(event, newcomer, actor=newcomer) is None


def test_unverified_bound_invite_refused_for_both_paths(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    newcomer = account("unverified")
    invite, code = create_invite(event, actor=actor, email=newcomer.email)
    with pytest.raises(NotFound):
        redeem_invite(event, code, newcomer, actor=newcomer)
    assert resolve_for_account(event, newcomer, actor=newcomer) is None
    event.registration_audience = "invite"; event.save()
    with pytest.raises(ValidationError, match="Verify your email"):
        register(event, member=newcomer, actor=newcomer)
    invite.refresh_from_db(); assert invite.uses == 0


def test_bulk_is_bounded_atomic_authorized_and_expiry_aware(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    with pytest.raises(ValidationError):
        bulk_invites(event, actor, [f"u{i}@example.test" for i in range(201)])
    with pytest.raises(PermissionDenied):
        bulk_invites(event, user, [user.email])
    with pytest.raises(ValidationError):
        bulk_invites(event, actor, [user.email, "invalid"])
    assert not event.invites.exists()
    invite, code = create_invite(event, actor=actor, email=user.email)
    invite.expires_at = timezone.now() - timedelta(seconds=1); invite.save()
    assert resolve_for_account(event, user, actor=user) is None
