"""Native staff scanner routes resolve their tenant from the scanned QR payload."""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from tests.accounts.native_helpers_m1d import attested_login, attested_staff_login
from tests.accounts.account_factories import make_staff
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import make_space, make_user
from tests.test_admin_direct_loans import make_product, make_qr

pytestmark = pytest.mark.django_db

RESOLVE = "/api/v1/admin/qr/resolve"


def bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture
def native_staff(settings, monkeypatch):
    home = make_space("native-qr-home")
    other = make_space("native-qr-other")
    user = make_staff(home, username="native-qr-staff", role_slug="inventory_manager",
                      password="strong-device-password")
    login, _ = attested_staff_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200
    return bearer(login.data["access"]), home, other


def test_native_staff_can_resolve_a_qr_of_the_selected_makerspace(native_staff):
    client, home, _other = native_staff
    qr = make_qr(home, make_product(home))

    response = client.post(RESOLVE, {"payload": qr.payload}, format="json",
                           HTTP_X_MAKERSPACE_ID=str(home.pk))

    assert response.status_code == 200
    assert response.data["qr"]["id"] == qr.id


def test_native_staff_cannot_resolve_another_makerspaces_qr_under_its_header(native_staff):
    client, home, other = native_staff
    foreign = make_qr(other, make_product(other))

    response = client.post(RESOLVE, {"payload": foreign.payload}, format="json",
                           HTTP_X_MAKERSPACE_ID=str(home.pk))

    assert response.status_code == 403


def test_native_staff_scanner_still_requires_the_header(native_staff):
    client, home, _other = native_staff
    qr = make_qr(home, make_product(home))

    assert client.post(RESOLVE, {"payload": qr.payload}, format="json").status_code == 403


def test_unknown_payload_reaches_the_view_and_404s(native_staff):
    client, home, _other = native_staff

    response = client.post(RESOLVE, {"payload": "not-a-real-qr"}, format="json",
                           HTTP_X_MAKERSPACE_ID=str(home.pk))

    assert response.status_code == 404


def test_member_and_staff_same_contact_keep_separate_grant_authority(settings, monkeypatch):
    space = make_space("native-qr-separate")
    member = make_user("native-qr-member", password="strong-device-password")
    # Release 2: two people never share an email (uniq_person_email); still two accounts.
    staff = make_staff(space, username="native-qr-staff", role_slug="inventory_manager",
                       email="native-qr-staff@e.com", password="strong-device-password")
    first, _ = attested_login(APIClient(), member, settings, monkeypatch)
    assert first.data["user"]["session_authority"] == "member"
    second, _ = attested_staff_login(APIClient(), staff, settings, monkeypatch)
    assert second.status_code == 200
    assert AccessToken(second.data["access"])["surface"] == "member"
    assert second.data["user"]["session_authority"] == "native_staff"
    assert first.data["user"]["id"] != second.data["user"]["id"]


def test_query_scoped_listing_requires_matching_query_target(native_staff):
    client, home, other = native_staff
    url = "/api/v1/admin/audit-logs"

    assert client.get(url, HTTP_X_MAKERSPACE_ID=str(home.pk)).status_code == 403
    assert client.get(f"{url}?makerspace={other.pk}",
                      HTTP_X_MAKERSPACE_ID=str(home.pk)).status_code == 403
    assert client.get(f"{url}?makerspace={home.pk}",
                      HTTP_X_MAKERSPACE_ID=str(home.pk)).status_code == 200


@pytest.mark.parametrize("kind", ["boxes", "containers", "tools"])
def test_native_qr_creation_uses_the_required_body_tenant(native_staff, kind):
    from apps.boxes.models import Box, QrCode
    client, home, other = native_staff
    url = f"/api/v1/admin/qr/{kind}"
    data = {"makerspace_id": home.pk}
    if kind == "tools":
        data["product_id"] = make_product(home).pk
    else:
        data["label"] = "Native box"
    before = Box.objects.count(), QrCode.objects.count()
    # A foreign selection cannot override the staff account's immutable tenant.
    assert client.post(url, data, format="json",
                       HTTP_X_MAKERSPACE_ID=str(other.pk)).status_code == 403
    assert client.post(url, data, format="json").status_code == 403
    assert client.post(url, {k: v for k, v in data.items() if k != "makerspace_id"},
                       format="json", HTTP_X_MAKERSPACE_ID=str(home.pk)).status_code == 403
    assert (Box.objects.count(), QrCode.objects.count()) == before

    result = client.post(url, data, format="json", HTTP_X_MAKERSPACE_ID=str(home.pk))
    assert result.status_code == 201
    assert result.data["makerspace"] == home.pk
