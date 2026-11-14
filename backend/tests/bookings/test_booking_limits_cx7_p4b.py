"""Alternate booking admissions share the tenant-wide active/monthly capacity."""
from datetime import timedelta

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.bookings import services
from apps.bookings.models import Booking, BookingOrganizationLink
from apps.bookings.organization_booking import book_for_organization
from apps.payments.models import Payment
from tests.bookings.test_organization_booking import _world
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]
KINDS = ["member", "staff", "house", "organization", "restore"]


def setup(kind, key):
    space, staff, room, member, org = _world("cx7-p4b-booking")
    space.enabled_features = sorted((set(space.enabled_features) | {"bookings.staff_tools"})
                                    - {"charges.enabled", "charges.bookings"})
    space.enabled_modules = [key for key in space.enabled_modules if key != "payments"]
    space.save(update_fields=["enabled_features", "enabled_modules"])
    rows = []
    if kind == "restore":
        for index in range(2):
            start = timezone.now() + timedelta(days=3 + index)
            row = services.create_booking(room, member=member, starts_at=start, ends_at=start + timedelta(hours=1))
            rows.append(services.cancel_booking(row, actor=staff))
    space.resource_limit_overrides = {key: 1}
    if kind == "restore":
        space.resource_limit_overrides["bookings_monthly"] = 0  # already-counted admissions are exempt
    space.save(update_fields=["resource_limit_overrides"])
    return space, staff, room, member, org, rows


def create(w, kind, index):
    _, staff, room, member, org, rows = w
    start = timezone.now() + timedelta(days=3 + index)
    values = {"starts_at": start, "ends_at": start + timedelta(hours=1)}
    if kind == "restore":
        return services.restore_booking(rows[index], actor=staff)
    if kind == "organization":
        return book_for_organization(staff, room, org, member, **values)
    if kind == "house":
        return services.create_booking(room, actor=staff, house=True, **values)
    return services.create_booking(room, member=member, actor=member if kind == "member" else staff, **values)


def snapshot():
    return [list(model.objects.order_by("pk").values())
            for model in (Booking, BookingOrganizationLink, Payment, AuditLog)]


CASES = [(kind, key) for kind in KINDS for key in ("bookings", "bookings_monthly")
         if kind != "restore" or key == "bookings"]


@pytest.mark.parametrize("kind,key", CASES)
def test_booking_creator_max_next_refusal_has_no_business_or_audit_writes(kind, key, settings):
    settings.MANAGED_PLANS_ENABLED = False
    w = setup(kind, key)
    assert create(w, kind, 0).status == "confirmed"
    before = snapshot()
    with pytest.raises(APIException) as failure:
        create(w, kind, 1)
    expected = (400, "limit_reached") if key == "bookings" else (409, "booking_quota_reached")
    assert (failure.value.status_code, str(failure.value.detail["code"])) == expected
    assert snapshot() == before
    assert Payment.objects.filter(makerspace=w[0]).count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind,key", CASES)
def test_booking_creators_at_last_tenant_slot_admit_one(kind, key, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w = setup(kind, key)
    expected = (400, "limit_reached") if key == "bookings" else (409, "booking_quota_reached")
    assert race_creators(lambda index: create(w, kind, index)) == [(201, "created"), expected]
    assert Booking.objects.filter(space__makerspace=w[0], status="confirmed").count() == 1
    action = "booking.restored" if kind == "restore" else "booking.created"
    assert AuditLog.objects.filter(makerspace=w[0], action=action).count() == 1
    assert Payment.objects.filter(makerspace=w[0]).count() == 0


@pytest.mark.parametrize("kind,key", [(kind, key) for kind, key in CASES if kind != "member"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_staff_booking_http_surfaces_preserve_exact_limit_code(kind, key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w = setup(kind, key)
    space, _, room, member, org, rows = w
    client = callers(space, surface, settings, monkeypatch)[0]

    def post(index):
        if kind == "restore":
            return client.post(reverse("admin-booking-restore", kwargs={"pk": rows[index].pk}), {}, format="json")
        start = timezone.now() + timedelta(days=3 + index)
        body = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat()}
        route = "admin-space-organization-booking" if kind == "organization" else "admin-space-booking-list"
        body.update({"organization_id": org.pk, "contact_member_id": member.pk} if kind == "organization"
                    else {"house": True} if kind == "house" else {"member_id": member.pk})
        return client.post(reverse(route, kwargs={"pk": room.pk}), body, format="json")

    assert post(0).status_code == (200 if kind == "restore" else 201)
    before = snapshot()
    refused = post(1)
    assert (refused.status_code, refused.json()["code"]) == ((400, "limit_reached") if key == "bookings"
                                                          else (409, "booking_quota_reached"))
    assert snapshot() == before


@pytest.mark.parametrize("kind", KINDS)
def test_booking_module_off_retains_rows_on_restores_with_rail_and_charges_off(kind, settings):
    settings.MANAGED_PLANS_ENABLED = False
    w = setup(kind, "bookings")
    saved = w[0].enabled_modules
    w[0].enabled_modules = [key for key in saved if key != "bookings"]
    w[0].save(update_fields=["enabled_modules"])
    w[2].makerspace = w[0]
    before = snapshot()
    with pytest.raises(APIException) as failure:
        create(w, kind, 0)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (
        404, "feature_disabled" if kind == "organization" else "module_disabled")
    assert snapshot() == before
    w[0].enabled_modules = saved
    w[0].save(update_fields=["enabled_modules"])
    assert create(w, kind, 0).status == "confirmed"
    assert Payment.objects.filter(makerspace=w[0]).count() == 0
