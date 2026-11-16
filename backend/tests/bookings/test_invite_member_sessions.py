"""Invitation acceptance crosses the session boundary only at its exact route."""

from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.authentication import _member_surface_path_allowed
from apps.accounts.reauthentication import stamp
from apps.audit.models import AuditLog
from apps.bookings.models import BookingSpaceStaffGrant
from apps.bookings.services_staff_grants import create_invite
from tests.bookings.staff_grant_helpers import grant_fixture

pytestmark = pytest.mark.django_db


def test_real_member_login_can_redeem_without_existing_staff_authority():
    tenant, manager, user, resource, grant, _ = grant_fixture()
    grant.delete()
    assert not user.makerspace_memberships.exists()
    invite, token = create_invite(resource, actor=manager, permissions=["check_in"], email=user.email)
    client = APIClient()
    login = client.post(reverse("auth-login"), {
        "username": user.username, "password": "Grant-password-123!", "surface": "member",
    }, format="json")
    assert login.status_code == 200, login.data
    assert AccessToken(login.data["access"])["surface"] == "member"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    staff_list = reverse("admin-booking-staff-invites", args=[resource.pk])
    revoke = reverse("admin-booking-staff-invite-revoke", args=[invite.pk])
    assert client.get(staff_list).status_code == 403
    assert client.post(revoke, {}, format="json").status_code == 403

    route = reverse("booking-staff-invite-redeem")
    # Redeeming takes on staff authority, so it needs a session-bound recent proof.
    refused = client.post(route, {"token": token}, format="json")
    assert refused.status_code == 403 and "recent_reauth_required" in str(refused.data)
    stamp(SimpleNamespace(user=user, auth=AccessToken(login.data["access"])))
    response = client.post(route, {"token": token}, format="json")
    assert response.status_code == 200, response.data
    assert response["Cache-Control"] == "private, no-store"
    accepted = BookingSpaceStaffGrant.objects.get(user=user, space=resource)
    assert accepted.makerspace_id == tenant.pk and accepted.permissions == ["check_in"]
    invite.refresh_from_db()
    assert invite.redeemed_by_id == user.pk and invite.redeemed_at is not None
    assert client.post(route, {"token": token}, format="json").status_code == 404
    assert AuditLog.objects.filter(action="booking.staff_grant_invite_redeemed", actor=user).count() == 1
    # A live delegated grant is usable from the same member session (V8).
    listing = client.get(reverse("admin-accessible-booking-spaces"))
    assert listing.status_code == 200
    assert {row["id"] for row in listing.data["results"]} == {resource.pk}
    assert client.get(staff_list).status_code == 403
    assert client.post(revoke, {}, format="json").status_code == 403


@pytest.mark.parametrize("domain", ["event", "booking"])
@pytest.mark.parametrize("suffix, allowed", [
    ("redeem", True), ("redeem/", True), ("", False),
    ("redeem/extra", False), ("redeem-extra", False), ("1/revoke/", False),
])
def test_member_invite_exception_is_exact_and_preserves_events(domain, suffix, allowed):
    assert _member_surface_path_allowed(f"/api/v1/admin/{domain}-staff-invites/{suffix}") is allowed
