"""Real database report contracts; unrun until composed and admitted."""
from datetime import timedelta

import pytest
from django.utils import timezone
from django.urls import reverse
from rest_framework.exceptions import APIException

from apps.bookings.models import BookableSpace, Booking
from apps.bookings.models_loan_context import BookingLoanContext
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, PublicToolLoan
from apps.makerspaces.models import MakerspaceMembership
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.operations import reports
from apps.operations.reports_loan_context import build_loan_purpose_summary
from apps.operations.reports_loan_context_details import build_booking_equipment, build_event_equipment
from tests.test_request_workflow import make_space, make_member, make_product, make_hardware_request, authenticated_client

pytestmark = pytest.mark.django_db


def setup_reports(slug="linked-equipment-reports"):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports", "events", "bookings", "request_workflow"})
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.enabled", "inventory.self_checkout"})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    actor = make_member(slug + "-manager", space)
    product = make_product(space)
    requests = [make_hardware_request(space, product, status=HardwareRequest.Status.ISSUED) for _ in range(4)]
    HardwareRequest.objects.filter(pk__in=[row.pk for row in requests]).update(issued_at=timezone.now())
    start = timezone.now() + timedelta(days=1)
    event = Event.objects.create(makerspace=space, title="Private event sentinel", starts_at=start, ends_at=start + timedelta(hours=1))
    resource = BookableSpace.objects.create(makerspace=space, name="Room")
    booking = Booking.objects.create(space=resource, name="Private booker sentinel", email="private-booker-sentinel@example.test", starts_at=start, ends_at=start + timedelta(hours=1))
    for request in requests[1::2]:
        EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    for request in requests[2:]:
        BookingLoanContext.objects.create(makerspace=space, request=request, booking=booking, active=True)
    return space, actor, product, requests, event, booking


def test_four_purposes_count_canonical_parent_once_with_multiple_items_and_adapters():
    space, actor, product, requests, event, booking = setup_reports()
    second_product = make_product(space, name="Second product")
    HardwareRequestItem.objects.create(request=requests[3], product=second_product, requested_quantity=2)
    for source in PublicToolLoan.Source.values:
        parent = make_hardware_request(space, product, status=HardwareRequest.Status.ISSUED)
        HardwareRequest.objects.filter(pk=parent.pk).update(issued_at=timezone.now())
        PublicToolLoan.objects.create(makerspace=space, request=parent, requester=parent.requester,
            source=source, target_type="product", target_id=product.pk, target_label=product.name)
    result = build_loan_purpose_summary(space.pk, actor=actor)
    grouped = {}
    for row in result.records:
        grouped[row["context"]] = grouped.get(row["context"], 0) + row["count"]
    assert grouped == {"Ordinary loan": 3, "Event": 1, "Booking": 1, "Event and booking": 1}
    assert sum(row["count"] for row in result.records) == 6
    assert result.meta["context_dimensions_available"] is True


@pytest.mark.parametrize("off", [("events",), ("bookings",), ("events", "bookings")])
def test_unavailable_dimension_never_identifies_individual_private_links(off):
    space, actor, product, requests, event, booking = setup_reports()
    space.enabled_modules = [key for key in space.enabled_modules if key not in off]
    space.save(update_fields=["enabled_modules"])
    result = build_loan_purpose_summary(space.pk, actor=actor)
    assert {row["context"] for row in result.records} == {"Context not shown"}
    assert sum(row["count"] for row in result.records) == 4
    assert result.meta["context_dimensions_available"] is False
    assert EventLoanContext.objects.filter(makerspace=space).count() == 2
    assert BookingLoanContext.objects.filter(makerspace=space).count() == 2


def test_inventory_only_reader_gets_uniform_undisclosed_summary_and_no_private_detail():
    space, actor, product, requests, event, booking = setup_reports()
    inventory = make_member("linked-inventory-manager", space,
        membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)
    result = build_loan_purpose_summary(space.pk, actor=inventory)
    assert {row["context"] for row in result.records} == {"Context not shown"}
    assert sum(row["count"] for row in result.records) == 4
    with pytest.raises(APIException):
        build_event_equipment(space.pk, actor=inventory, subject_kind="event", subject_id=event.pk)
    with pytest.raises(APIException):
        build_booking_equipment(space.pk, actor=inventory, subject_kind="booking", subject_id=booking.pk)


def test_exact_event_and_booking_details_are_scoped_and_exclude_private_fields():
    space, actor, product, requests, event, booking = setup_reports()
    event_result = reports.report_data("event-equipment", space.pk, actor=actor,
        report_filters={"subject_kind": "event", "subject_id": event.pk})
    booking_result = reports.report_data("booking-equipment", space.pk, actor=actor,
        report_filters={"subject_kind": "booking", "subject_id": booking.pk})
    assert {row["request_id"] for row in event_result["typed_rows"]} == {requests[1].pk, requests[3].pk}
    assert {row["request_id"] for row in booking_result["typed_rows"]} == {requests[2].pk, requests[3].pk}
    assert all(row["count"] == 1 for result in (event_result, booking_result) for row in result["typed_rows"])
    assert "Private event sentinel" not in str(event_result)
    assert "Private booker sentinel" not in str(booking_result)
    foreign = make_space("other-linked-reports")
    with pytest.raises(APIException):
        build_event_equipment(foreign.pk, actor=actor, subject_kind="event", subject_id=event.pk)


def test_date_filter_and_limit_apply_to_authorized_request_cohort():
    space, actor, product, requests, event, booking = setup_reports()
    start = timezone.now() - timedelta(hours=1)
    HardwareRequest.objects.filter(pk=requests[1].pk).update(issued_at=start - timedelta(days=1))
    result = build_event_equipment(space.pk, actor=actor, subject_kind="event", subject_id=event.pk,
        date_range=(start, timezone.now() + timedelta(hours=1)), limit=1)
    assert [row["request_id"] for row in result.records] == [requests[3].pk]


def test_never_issued_requests_are_excluded_but_returned_loan_is_retained():
    space, actor, product, requests, event, booking = setup_reports()
    for status in (HardwareRequest.Status.DRAFT, HardwareRequest.Status.PENDING_APPROVAL,
                   HardwareRequest.Status.ACCEPTED, HardwareRequest.Status.REJECTED,
                   HardwareRequest.Status.CANCELLED, HardwareRequest.Status.EXPIRED):
        request = make_hardware_request(space, product, status=status)
        EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    returned = make_hardware_request(space, product, status=HardwareRequest.Status.RETURNED)
    HardwareRequest.objects.filter(pk=returned.pk).update(issued_at=timezone.now() - timedelta(hours=1), closed_at=timezone.now())
    EventLoanContext.objects.create(makerspace=space, request=returned, event=event, active=True)
    result = build_loan_purpose_summary(space.pk, actor=actor)
    assert sum(row["count"] for row in result.records) == 5
    details = build_event_equipment(space.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    assert {row["request_id"] for row in details.records} == {requests[1].pk, requests[3].pk, returned.pk}


def test_exact_booking_http_preview_and_download_audit_use_authoritative_tenant():
    space, actor, product, requests, event, booking = setup_reports()
    api = authenticated_client(actor)
    filters = {"subject_kind": "booking", "subject_id": booking.pk}
    preview = api.get(reverse("analytics-generic", args=[space.pk, "booking-equipment"]), filters)
    assert preview.status_code == 200, getattr(preview, "data", None)
    assert {row["request_id"] for row in preview.data["typed_rows"]} == {requests[2].pk, requests[3].pk}
    assert AuditLog.objects.filter(makerspace=space, action="report.previewed", target_id=str(booking.pk)).exists()
    exported = api.get(reverse("report-export", args=[space.pk, "booking-equipment"]), filters)
    assert exported.status_code == 200, getattr(exported, "data", None)
    text = exported.content.decode("utf-8")
    assert "booking-equipment" in text.splitlines()[0]
    assert "subject_kind" in text.splitlines()[0]
    assert "Private booker sentinel" not in text
    assert AuditLog.objects.filter(makerspace=space, action="report.downloaded").exists()


def test_summary_availability_survives_real_projection_and_http_response():
    space, actor, product, requests, event, booking = setup_reports()
    api = authenticated_client(actor)
    response = api.get(reverse("analytics-generic", args=[space.pk, "loan-purpose-summary"]))
    assert response.status_code == 200, getattr(response, "data", None)
    assert response.data["meta"]["context_dimensions_available"] is True
    space.enabled_modules = [key for key in space.enabled_modules if key != "events"]
    space.save(update_fields=["enabled_modules"])
    response = api.get(reverse("analytics-generic", args=[space.pk, "loan-purpose-summary"]))
    assert response.status_code == 200, getattr(response, "data", None)
    assert response.data["meta"]["context_dimensions_available"] is False
    assert {row["context"] for row in response.data["typed_rows"]} == {"Context not shown"}
    exported = api.get(reverse("report-export", args=[space.pk, "loan-purpose-summary"]))
    assert exported.status_code == 200, getattr(exported, "data", None)
    text = exported.content.decode("utf-8")
    assert "loan-purpose-summary" in text.splitlines()[0]
    assert "Context not shown" in text
    assert "Private event sentinel" not in text
