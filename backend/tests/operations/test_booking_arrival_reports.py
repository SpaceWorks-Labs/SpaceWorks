"""Arrival counts are tenant/resource/window scoped, never measured usage."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.bookings import services
from apps.bookings.models import Booking
from apps.bookings.services_arrival import confirm_arrival, qr_value, reverse_arrival
from apps.operations.report_definitions_bookings import ARRIVAL_FIELDS, BOOKING_REPORT_DEFINITIONS
from apps.operations.reports_booking_resources import build_resource_utilization, build_resource_utilization_pdf
from apps.operations.reports_bookings import build_booking_utilization
from apps.operations.serializers_reports_bookings import BookingResourceUtilizationReportSerializer
from tests.bookings.staff_grant_helpers import grant_fixture
from tests.bookings.test_arrival_staff_tools_integration import arrival_world, clock
from tests.bookings.test_staff_tools_helpers import reserve

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("pdf", [False, True])
def test_arrival_counts_reuse_reservation_overlap_and_preserve_occupancy(monkeypatch, pdf):
    w = arrival_world(monkeypatch)
    start = w.row.starts_at
    completed_arrival = reserve(w, starts_at=start + timedelta(hours=2))
    reversed_arrival = reserve(w, starts_at=start + timedelta(hours=4))
    completed_without_arrival = reserve(w, starts_at=start + timedelta(hours=6))
    # Half-open boundaries: these two reservations only touch the selected window.
    boundary_start = reserve(w, starts_at=start + timedelta(hours=8))
    # Seed a historical overlap directly; ordinary admission would reject it.
    boundary_end = Booking.objects.create(space=w.resource, name="Boundary", email="boundary@example.test",
                                         phone="123", starts_at=start - timedelta(minutes=30),
                                         ends_at=start + timedelta(minutes=30))
    for row in (w.row, completed_arrival, reversed_arrival, boundary_start, boundary_end):
        clock(monkeypatch, row.starts_at)
        confirm_arrival(w.resource, qr_value(row), actor=w.actor)
    clock(monkeypatch, start + timedelta(hours=8))
    services.complete_booking(completed_arrival, actor=w.actor)
    services.complete_booking(completed_without_arrival, actor=w.actor)
    reverse_arrival(reversed_arrival, actor=w.actor)
    # Same tenant, different resource, plus a different tenant: neither may leak in.
    other_space = type(w.resource).objects.create(makerspace=w.tenant, name="Other room")
    _, _, _, foreign_space, _, _ = grant_fixture(slug="foreign-arrival-reports")
    for space in (other_space, foreign_space):
        Booking.objects.create(space=space, name="Other", email="other@example.test", phone="123",
                               starts_at=start, ends_at=start + timedelta(hours=1), arrived_at=start)
    bounds = (start + timedelta(minutes=30), start + timedelta(hours=8))
    args = dict(subject_kind="bookable_space", subject_id=w.resource.pk, date_range=bounds)
    legacy = build_booking_utilization(w.tenant.pk, **args)
    builder = build_resource_utilization_pdf if pdf else build_resource_utilization
    result = builder(w.tenant.pk, **args)
    row = result.records[0]
    assert len(result.records) == 1 and row["space_id"] == w.resource.pk
    assert row["arrived_reservations"] == 2  # confirmed + completed; reversed excluded
    assert row["confirmed_without_recorded_arrival"] == 1
    assert row["reserved_hours"] == Decimal("3.50")
    assert result.meta["arrival_counts_available"] is True
    assert result.field_order == (*legacy.field_order, *ARRIVAL_FIELDS)
    assert {key: row[key] for key in legacy.field_order} == legacy.records[0]
    assert build_booking_utilization(w.tenant.pk, **args) == legacy
    definition = next(d for d in BOOKING_REPORT_DEFINITIONS if d.key == (
        "booking-resource-utilization-pdf" if pdf else "booking-resource-utilization"))
    assert definition.fields == result.field_order and definition.version == 2
    assert BookingResourceUtilizationReportSerializer(data={
        "report_key": definition.key, "rows": [list(result.field_order)],
        "typed_rows": result.records,
        "meta": {"source": "live", "grain": "day", "rollup_through": None, **result.meta},
    }).is_valid(raise_exception=True)


def test_empty_arrival_history_is_zero_without_inferring_completion(monkeypatch):
    w = arrival_world(monkeypatch)
    clock(monkeypatch, w.row.ends_at)
    services.complete_booking(w.row, actor=w.actor)
    result = build_resource_utilization(w.tenant.pk, subject_kind="bookable_space", subject_id=w.resource.pk)
    assert result.records[0]["arrived_reservations"] == 0
    assert result.records[0]["confirmed_without_recorded_arrival"] == 0
    assert result.records[0]["window_hours"] is None
