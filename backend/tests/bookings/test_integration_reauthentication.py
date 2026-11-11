"""BK-H uses Lane F's real session proof on each booking grant mutation."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models_reauthentication import ReauthenticationSession
from apps.accounts.reauthentication import stamp
from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.bookings.models_staff_grants import BookingSpaceStaffGrant
from tests.bookings.staff_grant_helpers import grant_fixture

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("operation", ["invite", "update", "revoke", "invite_revoke"])
def test_grant_mutations_require_current_session_bound_proof(operation):
    from apps.bookings.services_staff_grants import create_invite
    tenant, manager, grantee, resource, grant, member = grant_fixture(slug="bkh-stepup")
    invite, raw = create_invite(resource, actor=manager, permissions=["edit_details"])
    refresh = SpaceWorksRefreshToken.for_user(manager)
    refresh["surface"] = "member"  # one account per person: a person token has the member surface
    access = refresh.access_token
    client = APIClient()
    client.force_authenticate(manager, token=access)
    method, path, payload = {
        "invite": ("post", f"spaces/{resource.pk}/staff-invites/", {"permissions": ["edit_details"]}),
        "update": ("patch", f"booking-staff-grants/{grant.pk}/", {"permissions": ["check_in"]}),
        "revoke": ("post", f"booking-staff-grants/{grant.pk}/revoke/", {}),
        "invite_revoke": ("post", f"booking-staff-invites/{invite.pk}/revoke/", {}),
    }[operation]
    def mutate():
        return getattr(client, method)("/api/v1/admin/" + path, payload, format="json")
    before = list(BookingSpaceStaffGrant.objects.values())
    response = mutate()
    assert response.status_code == 403
    assert "recent_reauth_required" in str(response.data)
    assert list(BookingSpaceStaffGrant.objects.values()) == before
    proof = stamp(SimpleNamespace(user=manager, auth=access, headers={}))
    ReauthenticationSession.objects.filter(pk=proof.pk).update(auth_time=timezone.now() - timedelta(minutes=11))
    assert mutate().status_code == 403
    stamp(SimpleNamespace(user=manager, auth=access, headers={}))
    # Another browser session cannot borrow the current session's proof.
    other = SpaceWorksRefreshToken.for_user(manager)
    other["surface"] = "member"
    client.force_authenticate(manager, token=other.access_token)
    assert mutate().status_code == 403
    client.force_authenticate(manager, token=access)
    assert mutate().status_code == (201 if operation == "invite" else 200)


def test_recent_proof_does_not_grant_delegation():
    tenant, manager, grantee, resource, grant, member = grant_fixture(slug="bkh-nondelegate")
    refresh = SpaceWorksRefreshToken.for_user(grantee)
    refresh["surface"] = "member"  # one account per person: a person token has the member surface
    access = refresh.access_token
    stamp(SimpleNamespace(user=grantee, auth=access, headers={}))
    client = APIClient()
    client.force_authenticate(grantee, token=access)
    response = client.post(f"/api/v1/admin/spaces/{resource.pk}/staff-invites/",
                           {"permissions": ["edit_details"]}, format="json")
    assert response.status_code in (403, 404)


def test_recent_proof_never_confers_cross_tenant_grant_authority():
    own = grant_fixture(slug="bkh-own-proof")
    foreign = grant_fixture(slug="bkh-foreign-proof")
    manager, resource, grant = own[1], foreign[3], foreign[4]
    refresh = SpaceWorksRefreshToken.for_user(manager)
    refresh["surface"] = "member"  # one account per person: a person token has the member surface
    access = refresh.access_token
    stamp(SimpleNamespace(user=manager, auth=access, headers={}))
    client = APIClient()
    client.force_authenticate(manager, token=access)
    assert client.post(f"/api/v1/admin/spaces/{resource.pk}/staff-invites/",
                       {"permissions": ["edit_details"]}, format="json").status_code in (403, 404)
    assert client.patch(f"/api/v1/admin/booking-staff-grants/{grant.pk}/",
                        {"permissions": ["check_in"]}, format="json").status_code in (403, 404)
    grant.refresh_from_db()
    assert grant.permissions == ["edit_details"]


def test_invitation_redemption_uses_the_same_recent_proof():
    from apps.bookings.services_staff_grants import create_invite
    tenant, manager, grantee, resource, grant, member = grant_fixture(slug="bkh-redeem")
    invite, raw = create_invite(resource, actor=manager, permissions=["edit_details"])
    refresh = SpaceWorksRefreshToken.for_user(grantee)
    refresh["surface"] = "member"  # one account per person: a person token has the member surface
    access = refresh.access_token
    client = APIClient()
    client.force_authenticate(grantee, token=access)
    path = "/api/v1/admin/booking-staff-invites/redeem/"
    assert client.post(path, {"token": raw}, format="json").status_code == 403
    invite.refresh_from_db()
    assert invite.redeemed_at is None
    stamp(SimpleNamespace(user=grantee, auth=access, headers={}))
    assert client.post(path, {"token": raw}, format="json").status_code == 200
    invite.refresh_from_db()
    assert invite.redeemed_at is not None
