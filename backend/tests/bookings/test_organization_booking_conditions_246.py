"""Decision 246: role, switch, validation, isolation and replay matrix for organization bookings."""
import pytest
from rest_framework.test import APIClient

from apps.bookings.models import Booking, BookingOrganizationLink
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.bookings.test_organization_booking import FEATURE, _window, _world
from tests.fixed_roles.helpers import staff_account

pytestmark = pytest.mark.django_db(transaction=True)
SLUGS = [role.slug for role in ROLE_CATALOG]


def _client(account=None):
    client = APIClient()
    if account is not None:
        client.force_authenticate(account)
    return client


def _payload(org, member, window=None):
    window = window or _window()
    return {"organization_id": org.pk, "contact_member_id": member.pk,
            "starts_at": window["starts_at"].isoformat(), "ends_at": window["ends_at"].isoformat()}


def _urls(resource):
    base = f"/api/v1/admin/spaces/{resource.pk}/organization-bookings/"
    return base, base + "choices/"


@pytest.mark.parametrize("slug", SLUGS)
def test_choices_and_create_follow_manage_bookings_for_every_built_in_role(slug):
    tenant, _boss, resource, member, org = _world(f"obc-role-{slug}".replace("_", "-"))
    actor = staff_account(tenant, f"obc-actor-{slug}", slug)
    allowed = "manage_bookings" in ROLE_BY_SLUG[slug].granted_actions
    create_url, choices_url = _urls(resource)
    client = _client(actor)
    choices = client.get(choices_url)
    created = client.post(create_url, _payload(org, member), format="json")
    assert (choices.status_code == 200) is allowed
    assert (created.status_code == 201) is allowed
    if not allowed:
        assert choices.status_code in (403, 404) and created.status_code in (403, 404)
        assert not BookingOrganizationLink.objects.exists()


def test_anonymous_is_refused():
    _tenant, _boss, resource, member, org = _world("obc-anon")
    create_url, choices_url = _urls(resource)
    assert _client().get(choices_url).status_code in (401, 403)
    assert _client().post(create_url, _payload(org, member), format="json").status_code in (401, 403)


def test_both_routes_are_404_while_the_switch_is_off_and_nothing_is_booked():
    _tenant, boss, resource, member, org = _world("obc-off", feature=False)
    create_url, choices_url = _urls(resource)
    assert _client(boss).get(choices_url).status_code == 404
    assert _client(boss).post(create_url, _payload(org, member), format="json").status_code == 404
    assert not Booking.objects.exists()


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("organization_id"), lambda p: p.pop("contact_member_id"), lambda p: p.pop("starts_at"),
    lambda p: p.update(organization_id=0), lambda p: p.update(starts_at="not-a-date"),
    lambda p: p.update(ends_at=p["starts_at"]),
])
def test_validation_errors_are_400_and_book_nothing(mutate):
    _tenant, boss, resource, member, org = _world("obc-valid")
    body = _payload(org, member)
    mutate(body)
    response = _client(boss).post(_urls(resource)[0], body, format="json")
    assert response.status_code == 400
    assert not BookingOrganizationLink.objects.exists()


def test_contact_must_belong_to_the_organization_and_to_the_space():
    tenant, boss, resource, member, org = _world("obc-contact")
    outsider = staff_account(tenant, "obc-contact-outsider", "member")
    response = _client(boss).post(_urls(resource)[0], _payload(org, outsider), format="json")
    assert response.status_code == 400 and "contact_member_id" in response.json()
    missing = _client(boss).post(_urls(resource)[0], {**_payload(org, member), "contact_member_id": 99999999}, format="json")
    assert missing.status_code == 400


def test_a_manager_of_another_space_cannot_use_this_spaces_resource():
    _tenant, _boss, resource, member, org = _world("obc-iso-a")
    other_tenant, _other_boss, _r, _m, _o = _world("obc-iso-b")
    outsider = staff_account(other_tenant, "obc-iso-outsider", "space_manager")
    create_url, choices_url = _urls(resource)
    assert _client(outsider).get(choices_url).status_code in (403, 404)
    assert _client(outsider).post(create_url, _payload(org, member), format="json").status_code in (403, 404)
    assert not BookingOrganizationLink.objects.exists()


def test_the_same_window_cannot_be_booked_twice_for_one_resource():
    _tenant, boss, resource, member, org = _world("obc-clash")
    window = _window()
    first = _client(boss).post(_urls(resource)[0], _payload(org, member, window), format="json")
    second = _client(boss).post(_urls(resource)[0], _payload(org, member, window), format="json")
    assert first.status_code == 201
    assert second.status_code in (400, 409)
    assert BookingOrganizationLink.objects.count() == 1
