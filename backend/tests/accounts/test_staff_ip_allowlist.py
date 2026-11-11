"""S-C: the per-space staff IP allow-list (#110c, #128 C-2) guards staff routes, never sign-in."""

import pytest
from cryptography.fernet import Fernet
from rest_framework.test import APIClient

from apps.accounts.tokens import SpaceWorksRefreshToken
from apps.makerspaces import security_settings_registry as registry
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_security import MakerspaceSecurityPolicy
from tests.accounts.account_factories import grant_staff_role, make_staff
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db
PASSWORD = "Allow list password 52!"
ORIGIN = "http://localhost:5000"


@pytest.fixture(autouse=True)
def keys(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]


def allow(space, cidrs):
    row, _ = MakerspaceSecurityPolicy.objects.get_or_create(makerspace=space)
    MakerspaceSecurityPolicy.objects.filter(pk=row.pk).update(values={"security.staff_ip_allowlist": cidrs})


def client_for(user, address):
    from apps.accounts.mfa_policy import credential, stamp
    if not hasattr(user, "_enrolled"):
        enrolled(user)
        user._enrolled = True
    stamp(user, credential(user), "totp")
    api = APIClient(REMOTE_ADDR=address)
    token = SpaceWorksRefreshToken.for_user(user).access_token
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_ORIGIN=ORIGIN)
    return api


def test_rows_are_registered_with_their_scope():
    assert registry.get("security.staff_ip_allowlist").scope == registry.SPACE
    assert registry.get("security.captcha_on_sign_in").choices == ("off", "after_failures", "always")


def test_staff_routes_of_a_space_need_its_network_member_routes_never_do():
    space = Makerspace.objects.create(name="Allow", slug="allow-a")
    staff = make_staff(space, username="allow-staff", password=PASSWORD)
    allow(space, ["198.51.100.0/24"])
    inside = client_for(staff, "198.51.100.7")
    assert inside.get(f"/api/v1/admin/makerspaces/{space.pk}").status_code == 200
    outside = client_for(staff, "203.0.113.7")
    refused = outside.get(f"/api/v1/admin/makerspaces/{space.pk}")
    assert refused.status_code == 403 and refused.data["code"] == "staff_network_refused"
    assert outside.get("/api/v1/auth/me").status_code == 200
    login = APIClient().post("/api/v1/auth/login", {"username": staff.username, "password": PASSWORD},
                             format="json", REMOTE_ADDR="203.0.113.7", HTTP_ORIGIN=ORIGIN)
    assert login.status_code == 200  # sign-in itself is never refused by a space's allow-list


def test_an_empty_list_allows_any_address_and_other_spaces_are_unaffected():
    open_space = Makerspace.objects.create(name="Open", slug="allow-open")
    strict = Makerspace.objects.create(name="Strict", slug="allow-strict")
    staff = make_staff(open_space, username="allow-two", password=PASSWORD)
    grant_staff_role(staff, strict)
    allow(strict, ["198.51.100.0/24"])
    api = client_for(staff, "203.0.113.9")
    assert api.get(f"/api/v1/admin/makerspaces/{open_space.pk}").status_code == 200
    assert api.get(f"/api/v1/admin/makerspaces/{strict.pk}").status_code == 403


def test_space_less_staff_routes_use_the_strictest_across_the_persons_spaces():
    from django.test import RequestFactory

    from apps.accounts import staff_network
    first = Makerspace.objects.create(name="First", slug="allow-first")
    second = Makerspace.objects.create(name="Second", slug="allow-second")
    staff = make_staff(first, username="allow-strictest", password=PASSWORD)
    grant_staff_role(staff, second)
    allow(first, ["198.51.100.0/24"])
    allow(second, ["198.51.100.128/25"])
    inside_both = RequestFactory().get("/", REMOTE_ADDR="198.51.100.200")
    inside_one = RequestFactory().get("/", REMOTE_ADDR="198.51.100.5")
    assert staff_network.allowed(inside_both, staff, set()) is True
    assert staff_network.allowed(inside_one, staff, set()) is False
    assert staff_network.allowed(inside_one, staff, {first.pk}) is True


def test_control_sets_and_locks_list_choice_and_off_is_stricter_rows():
    from django.test import Client
    from django.urls import reverse

    from apps.accounts.models import User
    from apps.makerspaces import security_settings
    from apps.makerspaces.models_security import MakerspaceSecurityLock
    from tests.accounts.reauth_helpers import force_recent_control_login
    space = Makerspace.objects.create(name="Control", slug="allow-control")
    root = User.objects.create_user(username="root-allow", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)
    client = Client()
    force_recent_control_login(client, root)
    url = reverse("admin:makerspaces_makerspace_security", args=[space.pk])
    assert client.get(url).status_code == 200
    client.post(url, {"action": "set", "key": "security.staff_ip_allowlist", "value": "198.51.100.9/24, 2001:db8::/48"})
    client.post(url, {"action": "lock", "key": "security.captcha_on_sign_in", "value": "after_failures"})
    client.post(url, {"action": "lock", "key": "security.passkeys_allowed", "note": "authenticator only"})
    rows = {row["key"]: row for row in security_settings.effective(space)}
    assert rows["security.staff_ip_allowlist"]["value"] == ["198.51.100.0/24", "2001:db8::/48"]
    assert rows["security.captcha_on_sign_in"]["value"] == "after_failures"
    assert MakerspaceSecurityLock.objects.get(makerspace=space, key="security.passkeys_allowed").floor is False
    assert b"198.51.100.0/24" in client.get(url).content
