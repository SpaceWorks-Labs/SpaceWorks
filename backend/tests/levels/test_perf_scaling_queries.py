"""Performance smoke: the hottest list endpoints cost the same number of queries at 10 rows as at 200.

A ceiling (see tests/perf) lets a per-row query hide under it; comparing a small page with a full page of the
SAME endpoint does not. Each case seeds 10 rows, measures, seeds up to 200, measures again, and requires the
full page to cost no more than two extra queries (a count or prefetch may appear once, never per row).
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS
from tests.fixed_roles.helpers import staff_account
from tests.member_submission import active_member_client
from tests.return_helpers import authenticated_client, make_accepted_request, make_product, make_space

pytestmark = pytest.mark.django_db
SMALL, LARGE, SLACK = 10, 200, 2


@pytest.fixture
def space():
    s = make_space("lvl-perf")
    s.enabled_modules, s.enabled_features = sorted(MODULE_KEYS), sorted(FEATURES)
    s.public_inventory_enabled = True
    s.save(update_fields=["enabled_modules", "enabled_features", "public_inventory_enabled"])
    return s


def _count(client, url):
    from django.core.cache import cache
    cache.clear()
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    assert response.status_code == 200, (url, response.status_code, response.content[:200])
    return len(ctx), response.json()


def _flat(client, url, grow):
    grow(0, SMALL)
    small, _ = _count(client, url)
    grow(SMALL, LARGE)
    large, payload = _count(client, url)
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    assert len(rows) > SMALL, f"{url} returned {len(rows)} rows; the large page is not exercising the list"
    assert large <= small + SLACK, f"{url}: {small} queries at {SMALL} rows, {large} at {len(rows)} rows (per-row queries)"


def test_public_inventory_list_is_flat(space):
    _flat(APIClient(), f"/api/v1/public/{space.slug}/inventory/",
          lambda a, b: [make_product(space, name=f"T{i}") for i in range(a, b)])


def test_staff_inventory_list_is_flat(space):
    manager = authenticated_client(staff_account(space, "lvl-perf-inv", "space_manager"))
    _flat(manager, f"/api/v1/admin/makerspace/{space.pk}/inventory",
          lambda a, b: [make_product(space, name=f"T{i}") for i in range(a, b)])


def test_staff_pending_requests_list_is_flat(space):
    from apps.hardware_requests.models import HardwareRequest
    manager = authenticated_client(staff_account(space, "lvl-perf-req", "space_manager"))

    def grow(a, b):
        for i in range(a, b):
            req = make_accepted_request(space, make_product(space, name=f"R{i}"), 1)
            HardwareRequest.objects.filter(pk=req.pk).update(status=HardwareRequest.Status.PENDING_APPROVAL)
    _flat(manager, f"/api/v1/admin/makerspace/{space.pk}/pending-requests", grow)


def _events(space, a, b):
    start = timezone.now() + timedelta(days=2)
    Event.objects.bulk_create([Event(makerspace=space, title=f"E{i}", starts_at=start + timedelta(hours=i),
                                     ends_at=start + timedelta(hours=i + 1), status=Event.Status.PUBLISHED,
                                     is_public=True) for i in range(a, b)])


def test_public_events_list_is_flat(space):
    _flat(APIClient(), f"/api/v1/public/{space.slug}/events/", lambda a, b: _events(space, a, b))


def test_staff_events_list_is_flat(space):
    manager = authenticated_client(staff_account(space, "lvl-perf-ev", "space_manager"))
    _flat(manager, f"/api/v1/admin/makerspaces/{space.pk}/events/", lambda a, b: _events(space, a, b))


def test_staff_bookings_list_is_flat(space):
    manager = authenticated_client(staff_account(space, "lvl-perf-bk", "space_manager"))
    room = BookableSpace.objects.create(makerspace=space, name="Studio", is_public=True, is_active=True)
    start = timezone.now() + timedelta(days=2)

    def grow(a, b):
        Booking.objects.bulk_create([Booking(space=room, name=f"B{i}", email=f"b{i}@example.test", phone="1",
                                             starts_at=start + timedelta(hours=2 * i),
                                             ends_at=start + timedelta(hours=2 * i + 1),
                                             status=Booking.Status.CONFIRMED) for i in range(a, b)])
    _flat(manager, f"/api/v1/admin/makerspaces/{space.pk}/bookings/", grow)


def test_member_activity_is_flat(space):
    _user, member = active_member_client(space, "lvl-perf-member")
    manager_product = make_product(space, name="Loanable")

    def grow(a, b):
        for _ in range(a, b):
            make_accepted_request(space, manager_product, 1)
    # The member's own history is what the page lists; the endpoint must not grow with unrelated rows either.
    small, _ = _count(member, f"/api/v1/member/makerspaces/{space.pk}/activity")
    grow(0, LARGE)
    large, _ = _count(member, f"/api/v1/member/makerspaces/{space.pk}/activity")
    assert large <= small + SLACK


def test_report_catalogue_is_flat_in_tenant_data(space):
    manager = authenticated_client(staff_account(space, "lvl-perf-rep", "space_manager"))
    url = f"/api/v1/admin/makerspace/{space.pk}/reports/catalog"
    small, _ = _count(manager, url)
    for i in range(LARGE):
        make_product(space, name=f"T{i}")
    large, _ = _count(manager, url)
    assert large <= small + SLACK
