"""U-A2 surface policy: staff routes are admitted per request from a person's staff track."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.claim_route_types import AnonymousRead, Refused
from apps.accounts.claim_routes import CLAIM_ROUTES
from apps.accounts.delegated_routes import DELEGABLE, MEMBERSHIP_ONLY, route_class
from apps.accounts.models import User
from apps.accounts.services_device_tokens import issue_device_token_pair
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import device_grant, grant_staff_role, make_membership, make_staff
from tests.accounts.mfa_helpers import enrolled
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db


def settings_url(space):
    return f"/api/v1/admin/makerspaces/{space.pk}/security-settings"


@pytest.fixture
def spaces():
    a = Makerspace.objects.create(name="Track A", slug="track-a", frontend_domain="track-a.test",
                                  frontend_domain_status=Makerspace.DomainStatus.VERIFIED)
    b = Makerspace.objects.create(name="Track B", slug="track-b")
    return a, b


def test_staff_role_admits_its_space_only(spaces):
    a, b = spaces
    manager = make_staff(a, username="track-manager")
    api = bearer_client(manager)
    assert api.get(settings_url(a)).status_code == 200
    refused = api.get(settings_url(b))
    assert refused.status_code == 403


def test_community_membership_never_reaches_staff_routes(spaces):
    a, _b = spaces
    member = User.objects.create_user("track-member", password="x" * 20)
    make_membership(member, a)
    assert bearer_client(member).get(settings_url(a)).status_code == 403


def test_invalid_target_refuses(spaces):
    a, b = spaces
    manager = make_staff(a, username="track-invalid")
    grant_staff_role(manager, b)
    api = bearer_client(manager)
    assert api.get(settings_url(a) + "?makerspace=abc").status_code == 403
    # Two targets: the URL names A, the hint names B -- refused even though both are staff.
    assert api.get(settings_url(a) + f"?makerspace={b.pk}").status_code == 403


def test_verified_custom_origin_pins_targets(spaces):
    a, b = spaces
    person = make_staff(a, username="track-pinned")
    grant_staff_role(person, b)
    api = bearer_client(person)
    api.credentials(HTTP_AUTHORIZATION=api._credentials["HTTP_AUTHORIZATION"], HTTP_ORIGIN="https://track-a.test")
    assert api.get(settings_url(a)).status_code == 200
    assert api.get(settings_url(b)).status_code == 403


def _device_client(user, grant):
    access, _refresh, _family = issue_device_token_pair(user, grant)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def test_native_member_grant_never_carries_staff_authority(spaces):
    a, _b = spaces
    manager = make_staff(a, username="track-native-member")
    make_membership(manager, a)
    client = _device_client(manager, device_grant(manager))
    response = client.get(settings_url(a), HTTP_X_MAKERSPACE_ID=str(a.pk))
    assert response.status_code == 403
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.data["staff_roles"] == []
    assert me.data["session_authority"] == "member"


def test_native_staff_grant_is_fixed_to_its_tenant(spaces):
    a, b = spaces
    person = make_staff(a, username="track-native-staff")
    grant_staff_role(person, b)
    grant = device_grant(person, staff_makerspace_id=a.pk)
    row, _secret = enrolled(person)
    person._mfa_verified_version = str(row.version)
    person._mfa_method = "totp"  # S-A: staff proof names its factor
    client = _device_client(person, grant)
    assert client.get(settings_url(a)).status_code == 403  # header required
    assert client.get(settings_url(a), HTTP_X_MAKERSPACE_ID=str(a.pk)).status_code == 200
    assert client.get(settings_url(b), HTTP_X_MAKERSPACE_ID=str(b.pk)).status_code == 403
    me = client.get("/api/v1/auth/me")
    assert me.data["session_authority"] == "native_staff"
    assert [entry["makerspace"]["id"] for entry in me.data["staff_roles"]] == [a.pk]


def test_claim_sessions_never_reach_staff_routes():
    # The sign-in doors (auth-*, social-*, device-*) carry a historical membership-only label
    # but live under /api/v1/auth/, a member-surface path; the claim gate exempts those paths.
    doors = ("auth-", "social-", "device-")
    leaks = sorted(
        view for (view, _method), policy in CLAIM_ROUTES.items()
        if not isinstance(policy, (Refused, AnonymousRead))
        and route_class(view.rpartition(":")[2]) in {DELEGABLE, MEMBERSHIP_ONLY}
        and not view.rpartition(":")[2].startswith(doors)
    )
    assert leaks == []


def test_platform_superadmin_keeps_lane_d_surface(spaces):
    a, _b = spaces
    root = User.objects.create_superuser("track-root", email="root@track.test", password="x" * 20)
    assert bearer_client(root).get(settings_url(a)).status_code == 200
