"""Contract level: real responses from the surface the web, Android and iOS clients all generate against
validate against the documented schema (jsonschema), for whatever status the API actually returned.

A schema that drifts from the serializer is the failure a generated mobile client cannot recover from, so
each case here calls the endpoint with real rows behind it and checks the body field by field.
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS
from tests.fixed_roles.helpers import staff_account
from tests.levels.schema_tools import live_schema, response_problems
from tests.member_submission import active_member_client
from tests.return_helpers import authenticated_client, make_accepted_request, make_product, make_space

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    space = make_space("lvl-contract")
    space.enabled_modules, space.enabled_features = sorted(MODULE_KEYS), sorted(FEATURES)
    space.public_inventory_enabled = True
    space.save(update_fields=["enabled_modules", "enabled_features", "public_inventory_enabled"])
    products = [make_product(space, name=f"Tool {i}") for i in range(3)]
    make_accepted_request(space, products[0], 1)
    start = timezone.now() + timedelta(days=3)
    Event.objects.create(makerspace=space, title="Open night", starts_at=start, ends_at=start + timedelta(hours=2),
                         status=Event.Status.PUBLISHED, is_public=True)
    room = BookableSpace.objects.create(makerspace=space, name="Studio", is_public=True, is_active=True)
    Booking.objects.create(space=room, name="B", email="b@example.test", phone="1", starts_at=start,
                           ends_at=start + timedelta(hours=1), status=Booking.Status.CONFIRMED)
    manager = staff_account(space, "lvl-contract-manager", "space_manager")
    _member, member_client = active_member_client(space, "lvl-contract-member")
    return {"space": space, "room": room, "manager": authenticated_client(manager), "member": member_client,
            "anon": APIClient()}


def _cases(world):
    s, i, slug = world["space"], world["space"].pk, world["space"].slug
    return [
        ("anon", "/api/v1/public/makerspaces/", "/api/v1/public/makerspaces/"),
        ("anon", f"/api/v1/public/{slug}/inventory/", "/api/v1/public/{makerspace_slug}/inventory/"),
        ("anon", f"/api/v1/public/{slug}/inventory/categories/", "/api/public/{makerspace_slug}/inventory/categories/"),
        ("anon", f"/api/v1/public/{slug}/events/", "/api/v1/public/{makerspace_slug}/events/"),
        ("anon", f"/api/v1/public/{slug}/spaces/", "/api/v1/public/{makerspace_slug}/spaces/"),
        ("anon", f"/api/v1/public/{slug}/machines", "/api/v1/public/{makerspace_slug}/machines"),
        ("anon", f"/api/v1/public/{slug}/equipment-kits/", "/api/v1/public/{makerspace_slug}/equipment-kits/"),
        ("anon", f"/api/v1/public/{slug}/stats/", "/api/v1/public/{makerspace_slug}/stats/"),
        ("member", "/api/v1/auth/me", "/api/v1/auth/me"),
        ("member", f"/api/v1/member/makerspaces/{i}/activity", "/api/v1/member/makerspaces/{makerspace_id}/activity"),
        ("member", f"/api/v1/member/makerspaces/{i}/machines", "/api/v1/member/makerspaces/{makerspace_id}/machines"),
        ("member", f"/api/v1/member/makerspaces/{i}/payments", "/api/v1/member/makerspaces/{makerspace_id}/payments"),
        ("manager", f"/api/v1/admin/makerspace/{i}/inventory", "/api/v1/admin/makerspace/{makerspace_id}/inventory"),
        ("manager", f"/api/v1/admin/makerspace/{i}/direct-loans", "/api/v1/admin/makerspace/{makerspace_id}/direct-loans"),
        ("manager", f"/api/v1/admin/makerspace/{i}/dashboard", "/api/v1/admin/makerspace/{makerspace_id}/dashboard"),
        ("manager", f"/api/v1/admin/makerspace/{i}/machines", "/api/v1/admin/makerspace/{makerspace_id}/machines"),
        ("manager", f"/api/v1/admin/makerspace/{i}/payments", "/api/v1/admin/makerspace/{makerspace_id}/payments"),
        ("manager", f"/api/v1/admin/makerspace/{i}/reports/catalog", "/api/v1/admin/makerspace/{makerspace_id}/reports/catalog"),
        ("manager", f"/api/v1/admin/makerspaces/{i}/bookings/", "/api/v1/admin/makerspaces/{makerspace_id}/bookings/"),
        ("manager", f"/api/v1/admin/makerspaces/{i}/spaces/", "/api/v1/admin/makerspaces/{makerspace_id}/spaces/"),
        ("manager", f"/api/v1/admin/makerspaces/{i}/memberships", "/api/v1/admin/makerspaces/{makerspace_id}/memberships"),
        ("manager", f"/api/v1/admin/makerspaces/{i}/membership-plans", "/api/v1/admin/makerspaces/{makerspace_id}/membership-plans"),
    ]


def test_the_chosen_templates_exist_in_the_schema(world):
    paths = live_schema()["paths"]
    missing = [t for _who, _url, t in _cases(world) if t not in paths or "get" not in paths[t]]
    assert missing == []


def test_real_responses_conform_to_the_documented_schema(world):
    failures = []
    for who, url, template in _cases(world):
        response = world[who].get(url)
        try:
            payload = response.json()
        except ValueError:
            failures.append(f"GET {url}: {response.status_code} is not JSON")
            continue
        problems = response_problems("get", template, response.status_code, payload)
        failures += [f"GET {url} [{response.status_code}] {p}" for p in problems]
    assert not failures, "\n".join(failures)


def test_a_refusal_conforms_too(world):
    """The error a client must parse (anonymous on a staff route) matches the documented 401/403 body."""
    url, template = f"/api/v1/admin/makerspace/{world['space'].pk}/inventory", "/api/v1/admin/makerspace/{makerspace_id}/inventory"
    response = world["anon"].get(url)
    assert response.status_code in (401, 403)
    assert response_problems("get", template, response.status_code, response.json()) == []
