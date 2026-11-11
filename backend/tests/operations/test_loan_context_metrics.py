"""Decision 216 item 16: linked-loan metrics and per-subject timelines."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.accounts.models import User
from apps.audit import services as audit
from apps.events.models import Event
from apps.events.models_loan_context import EventLoanContext
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.makerspaces.models import MakerspaceMembership
from apps.operations import reports
from apps.operations.reports_loan_context import build_loan_purpose_summary
from apps.operations.reports_loan_context_details import build_event_equipment
from apps.operations.reports_loan_timeline import build_booking_loan_timeline, build_event_loan_timeline
from tests.operations.test_loan_context_reports import setup_reports
from tests.test_request_workflow import (
    authenticated_client, make_hardware_request, make_member, make_product, make_space,
)

pytestmark = pytest.mark.django_db


def _measure(request, **quantities):
    HardwareRequestItem.objects.filter(request=request).update(**quantities)


def setup_metrics(slug="linked-loan-metrics"):
    space, actor, product, requests, event, booking = setup_reports(slug)
    product.unit_cost, product.cost_unit, product.cost_currency = Decimal("10.00"), "count", "INR"
    product.save(update_fields=["unit_cost", "cost_unit", "cost_currency"])
    for request in requests:
        _measure(request, issued_quantity=1)
    # The both-context loan carries two items, one partly lost, and is overdue.
    both = requests[3]
    HardwareRequestItem.objects.create(request=both, product=make_product(space, name="Second"),
                                       requested_quantity=2, issued_quantity=2)
    HardwareRequestItem.objects.filter(request=both, product=product).update(missing_quantity=1)
    HardwareRequest.objects.filter(pk=both.pk).update(return_due_at=timezone.now() - timedelta(hours=2))
    return space, actor, product, requests, event, booking


def _by_context(result):
    grouped = {}
    for row in result.records:
        target = grouped.setdefault(row["context"], dict.fromkeys(
            ("count", "issued_units", "missing_units", "overdue_count", "unpriced_loss_loans"), 0))
        for field in target:
            target[field] += row[field]
    return grouped


def test_each_loan_counts_once_across_both_contexts_and_overall_totals():
    space, actor, product, requests, event, booking = setup_metrics()
    result = build_loan_purpose_summary(space.pk, actor=actor)
    grouped = _by_context(result)
    assert grouped["Event and booking"] == {"count": 1, "issued_units": 3, "missing_units": 1,
                                           "overdue_count": 1, "unpriced_loss_loans": 0}
    for context in ("Ordinary loan", "Event", "Booking"):
        assert grouped[context]["count"] == 1 and grouped[context]["issued_units"] == 1
    # Overall totals are column sums; the both-context loan and its two items are never doubled.
    assert sum(row["count"] for row in result.records) == 4
    assert sum(row["issued_units"] for row in result.records) == 6
    assert sum(row["overdue_count"] for row in result.records) == 1
    loss = [row for row in result.records if row["estimated_loss_cost"]]
    assert [(row["context"], row["currency"], row["estimated_loss_cost"]) for row in loss] == [
        ("Event and booking", "INR", Decimal("10.0000"))]
    assert all(row["loan_hours"] >= 0 for row in result.records)


def test_unpriced_missing_unit_is_counted_separately_not_costed_as_zero():
    space, actor, product, requests, event, booking = setup_metrics("linked-loan-unpriced")
    product.unit_cost = None
    product.save(update_fields=["unit_cost"])
    result = build_loan_purpose_summary(space.pk, actor=actor)
    row = next(row for row in result.records if row["context"] == "Event and booking")
    assert row["unpriced_loss_loans"] == 1 and row["currency"] == ""
    detail = build_event_equipment(space.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    both = next(row for row in detail.records if row["request_id"] == requests[3].pk)
    assert both["estimated_loss_cost"] is None and both["missing_units"] == 1 and both["overdue_count"] == 1


def test_subject_equipment_rows_carry_per_loan_metrics_once():
    space, actor, product, requests, event, booking = setup_metrics("linked-loan-detail")
    detail = reports.report_data("event-equipment", space.pk, actor=actor,
                                 report_filters={"subject_kind": "event", "subject_id": event.pk})
    rows = {row["request_id"]: row for row in detail["typed_rows"]}
    assert set(rows) == {requests[1].pk, requests[3].pk}
    assert rows[requests[3].pk]["issued_units"] == 3 and rows[requests[3].pk]["count"] == 1
    assert rows[requests[3].pk]["currency"] == "INR"
    assert rows[requests[1].pk]["overdue_count"] == 0


def test_event_timeline_orders_source_milestones_and_excludes_drafts():
    space, actor, product, requests, event, booking = setup_reports("linked-loan-timeline")
    now = timezone.now()
    closed = requests[1]
    HardwareRequest.objects.filter(pk=closed.pk).update(
        status=HardwareRequest.Status.CLOSED_WITH_ISSUE, created_at=now - timedelta(days=3),
        accepted_at=now - timedelta(days=2),
        issued_at=now - timedelta(days=1), closed_at=now)
    rejected = make_hardware_request(space, product, status=HardwareRequest.Status.REJECTED)
    audit.record(actor, "request.rejected", makerspace=space, target=rejected, meta={"reason": "x"})
    draft = make_hardware_request(space, product, status=HardwareRequest.Status.DRAFT)
    for request in (rejected, draft):
        EventLoanContext.objects.create(makerspace=space, request=request, event=event, active=True)
    result = build_event_loan_timeline(space.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    milestones = [(row["request_id"], row["milestone"]) for row in result.records]
    assert [m for pk, m in milestones if pk == closed.pk] == ["requested", "accepted", "issued", "closed_with_issue"]
    assert [m for pk, m in milestones if pk == rejected.pk] == ["requested", "rejected"]
    assert draft.pk not in {pk for pk, _ in milestones}
    assert requests[0].pk not in {pk for pk, _ in milestones}
    assert [row["occurred_at"] for row in result.records] == sorted(row["occurred_at"] for row in result.records)
    assert "Private event sentinel" not in str(result)
    windowed = build_event_loan_timeline(space.pk, actor=actor, subject_kind="event", subject_id=event.pk,
                                         date_range=(now - timedelta(days=1, hours=1), now - timedelta(hours=1)))
    assert [(row["request_id"], row["milestone"]) for row in windowed.records] == [(closed.pk, "issued")]


def test_both_context_loan_is_one_request_in_each_subject_timeline():
    space, actor, product, requests, event, booking = setup_reports("linked-loan-both-timeline")
    event_rows = build_event_loan_timeline(space.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    booking_rows = build_booking_loan_timeline(space.pk, actor=actor, subject_kind="booking", subject_id=booking.pk)
    assert {row["request_id"] for row in event_rows.records} == {requests[1].pk, requests[3].pk}
    assert {row["request_id"] for row in booking_rows.records} == {requests[2].pk, requests[3].pk}
    assert sum(row["milestone"] == "issued" and row["request_id"] == requests[3].pk
               for row in event_rows.records) == 1


@pytest.mark.parametrize("off", ["events", "request_workflow"])
def test_module_off_refuses_timeline_but_keeps_summary_totals(off):
    space, actor, product, requests, event, booking = setup_metrics(f"linked-loan-off-{off}")
    space.enabled_modules = [key for key in space.enabled_modules if key != off]
    space.save(update_fields=["enabled_modules"])
    with pytest.raises(APIException):
        build_event_loan_timeline(space.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    with pytest.raises(APIException):
        build_event_equipment(space.pk, actor=actor, subject_kind="event", subject_id=event.pk)
    if off == "events":
        result = build_loan_purpose_summary(space.pk, actor=actor)
        assert {row["context"] for row in result.records} == {"Context not shown"}
        assert sum(row["count"] for row in result.records) == 4
        assert sum(row["issued_units"] for row in result.records) == 6
        assert result.meta["context_dimensions_available"] is False
        # The booking timeline is independent of the events switch.
        assert build_booking_loan_timeline(space.pk, actor=actor, subject_kind="booking",
                                           subject_id=booking.pk).records


def test_timeline_requires_inventory_audit_and_subject_authority():
    space, actor, product, requests, event, booking = setup_reports("linked-loan-denied")
    inventory = make_member_inventory(space)
    for kind, subject, builder in (("event", event, build_event_loan_timeline),
                                   ("booking", booking, build_booking_loan_timeline)):
        with pytest.raises(APIException):
            builder(space.pk, actor=inventory, subject_kind=kind, subject_id=subject.pk)
    api = authenticated_client(inventory)
    response = api.get(reverse("analytics-generic", args=[space.pk, "event-loan-timeline"]),
                       {"subject_kind": "event", "subject_id": event.pk})
    assert response.status_code in (403, 404)
    owner = authenticated_client(actor)
    response = owner.get(reverse("analytics-generic", args=[space.pk, "event-loan-timeline"]),
                         {"subject_kind": "event", "subject_id": event.pk})
    assert response.status_code == 200, getattr(response, "data", None)
    assert {row["request_id"] for row in response.data["typed_rows"]} == {requests[1].pk, requests[3].pk}


def make_member_inventory(space):
    return make_member("linked-timeline-inventory", space,
                       membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER, role=User.Role.REQUESTER)


def test_cross_tenant_subject_and_space_are_refused():
    space, actor, product, requests, event, booking = setup_reports("linked-loan-tenant")
    foreign = make_space("linked-loan-foreign")
    foreign.enabled_modules = list(space.enabled_modules)
    foreign.save(update_fields=["enabled_modules"])
    for builder, kind, subject in ((build_event_loan_timeline, "event", event),
                                   (build_booking_loan_timeline, "booking", booking)):
        with pytest.raises(APIException):
            builder(foreign.pk, actor=actor, subject_kind=kind, subject_id=subject.pk)
    other = Event.objects.create(makerspace=foreign, title="Foreign", starts_at=event.starts_at, ends_at=event.ends_at)
    with pytest.raises((APIException, Http404)):
        build_event_loan_timeline(space.pk, actor=actor, subject_kind="event", subject_id=other.pk)
    with pytest.raises(APIException):
        build_event_loan_timeline(space.pk, actor=actor, subject_kind="booking", subject_id=booking.pk)
