from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.claim_sessions import attach_claim_context
from apps.accounts.models_claim import MemberClaimCode
from apps.audit.models import AuditLog
from apps.presence.models import PresencePreference
from apps.presence.services import start_session

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("existing,requested", [(None, True), (False, True), (True, False), (True, None)])
def test_claim_start_visibility_is_session_only(lane, existing, requested):
    user, space = lane.owner, lane.space
    user.is_walk_in = True
    user.set_unusable_password()
    user.save(update_fields=["is_walk_in", "password"])
    if existing is not None:
        PresencePreference.objects.create(makerspace=space, account=user, hide_on_display=existing)
    deadline = timezone.now() + timedelta(minutes=90)
    claim = MemberClaimCode.objects.create(membership=user.makerspace_memberships.get(makerspace=space),
        code_digest="c" * 64, issued_by=lane.staff, expires_at=deadline,
        consumed_at=timezone.now(), absolute_expires_at=deadline)
    attach_claim_context(user, claim)
    session = start_session(user, space, 60, latitude=0, longitude=0, accuracy=1, hide_on_display=requested)
    assert session.hide_on_display == (existing if requested is None else requested)
    assert session.created_via_claim_session_id == claim.pk
    stored = PresencePreference.objects.filter(makerspace=space, account=user).first()
    assert (stored.hide_on_display if stored else None) == existing
    assert not AuditLog.objects.filter(makerspace=space, action="presence.preference_updated").exists()


def test_ordinary_account_start_still_saves_visibility_default(lane):
    start_session(lane.owner, lane.space, 60, latitude=0, longitude=0, accuracy=1, hide_on_display=True)
    assert PresencePreference.objects.get(makerspace=lane.space, account=lane.owner).hide_on_display
