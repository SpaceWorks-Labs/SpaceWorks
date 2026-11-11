"""Departure stops tenant push without revoking a member's global device grant."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.integrations.models import PushDevice
from apps.makerspaces.membership_revocation import revoke_membership
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.return_helpers import make_member, make_space, make_user
from tests.accounts.account_factories import device_grant, make_membership
from tests.test_native_push import device_client

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("action", ["revoke", "leave"])
def test_departure_deactivates_only_users_push_in_departed_makerspace(action):
    space = make_space("push-departure")
    other_space = make_space("push-staying")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"membership", "member_accounts"})
    space.enabled_features = sorted(set(space.enabled_features) | {"membership.self_service"})
    space.save()
    manager = make_member("push-manager", space)
    user = make_user("push-departing-user", access_status="active")
    member_role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    membership = MakerspaceMembership.objects.create(
        user=user, makerspace=space, assigned_role=member_role, role="custom",
    )
    other_membership = make_membership(user, other_space)
    _, grant = device_client(user, space)
    # The manager is a separate tenant-bound staff account with its own staff grant.
    foreign_grant = device_grant(manager, platform="apple")

    def push(owner, tenant, device_grant, key, **extra):
        row = PushDevice(
            user=owner, makerspace=tenant, device_grant=device_grant,
            provider="apns", environment="development", token_fingerprint=key * 64, **extra,
        )
        row.set_token(f"push-secret-{key}")
        row.save()
        return row

    departed = [push(user, space, grant, "a"), push(user, space, grant, "b")]
    retained = push(user, other_space, grant, "c")
    foreign = push(manager, space, foreign_grant, "d")
    previous_invalidation = timezone.now()
    inactive = push(user, space, grant, "e", active=False, invalidated_at=previous_invalidation)
    before = timezone.now()
    if action == "revoke":
        revoke_membership(manager, membership, "Membership ended")
    else:
        client = APIClient()
        client.force_authenticate(user)
        response = client.post(f"/api/v1/member/makerspaces/{space.pk}/account/leave", {
            "reason": "Moving away",
        }, format="json")
        assert response.status_code == 200
    after = timezone.now()

    membership.refresh_from_db()
    assert membership.status == "revoked"
    for row in departed:
        row.refresh_from_db()
        assert not row.active and before <= row.invalidated_at <= after
    for row in (retained, foreign):
        row.refresh_from_db()
        assert row.active and row.invalidated_at is None
    inactive.refresh_from_db()
    assert not inactive.active and inactive.invalidated_at == previous_invalidation
    grant.refresh_from_db()
    other_membership.refresh_from_db()
    assert grant.status == "active" and grant.revoked_at is None
    assert other_membership.status == "active"
    event = "membership.revoked" if action == "revoke" else "membership.left"
    assert AuditLog.objects.filter(action=event, makerspace=space, target_id=str(membership.pk)).exists()
