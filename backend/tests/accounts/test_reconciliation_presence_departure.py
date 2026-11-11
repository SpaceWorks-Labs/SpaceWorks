"""Account-only presence ends at archive even when its module is now disabled."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.account_deletion import request_deletion
from apps.audit.models import AuditLog
from apps.presence.models import PresenceSession
from tests.accounts.test_support_m1d import account, proven, m1d_config
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def test_archiving_account_only_guest_ends_presence_without_module_or_membership_gate():
    user, other = account(), account()
    space = make_space("departing-guest-presence")
    now = timezone.now()
    own = PresenceSession.objects.create(account=user, member=user, makerspace=space, status="guest",
        started_at=now, expires_at=now + timedelta(hours=1))
    foreign = PresenceSession.objects.create(account=other, member=other, makerspace=space, status="guest",
        started_at=now, expires_at=now + timedelta(hours=1))
    space.enabled_modules = []
    space.save(update_fields=["enabled_modules"])
    assert not user.makerspace_memberships.exists()
    request_deletion(proven(user))
    own.refresh_from_db()
    foreign.refresh_from_db()
    assert own.ended_at and own.end_reason == "user_ended" and own.ended_by_id == user.pk
    assert foreign.ended_at is None
    assert AuditLog.objects.filter(action="presence.ended", actor=user, target_id=str(own.pk)).exists()
