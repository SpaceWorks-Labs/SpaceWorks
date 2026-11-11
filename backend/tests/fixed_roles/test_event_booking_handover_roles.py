"""Fixed duties reach their workflows and retain their authority boundaries."""
import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.bookings.models import BookableSpace
from apps.evidence.storage import EvidenceValidationResult
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.machines.models import Machine, MachineType, MachineServiceRequest, ServiceBucket
from apps.operations.report_registry import REPORT_DEFINITIONS
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.handout_roles import make_handout_member
from tests.return_helpers import (
    authenticated_client, make_space, make_user, make_return_evidence,
    return_payload, return_url,
)
from tests.test_issue import (
    assign_scanned_box, issue_url, make_accepted_request, make_box,
    make_issue_evidence, make_product,
)
from tests.test_admin_direct_loans import direct_payload, direct_url, eligible_member

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("slug,report", [
    ("event_manager", "event-attendance"),
    ("booking_manager", "booking-utilization"),
])
def test_duty_reports_and_dashboard_are_accessible(slug, report):
    space = make_space(f"duty-{slug}")
    actor = make_user(f"duty-{slug}", access_status="active", account_kind="staff", staff_makerspace=space)
    assign_builtin_roles(actor, space, slug)
    client = authenticated_client(actor)
    assert client.get(reverse("operations-dashboard", args=[space.pk])).status_code == 200
    assert client.get(reverse(f"analytics-{report}", args=[space.pk])).status_code == 200
    catalog = client.get(reverse("report-catalog", args=[space.pk]))
    assert catalog.status_code == 200
    keys = {row["key"] for row in catalog.data["results"]}
    assert report in keys
    audit_reports = {definition.key for definition in REPORT_DEFINITIONS
                     if definition.required_action == rbac.Action.VIEW_AUDIT}
    assert keys.isdisjoint(audit_reports)
    assert client.get(reverse("analytics-most-lent", args=[space.pk])).status_code == 404
    assert not rbac.can(actor, rbac.Action.VIEW_AUDIT, space.pk)


def test_booking_manager_reads_and_changes_booking_rules():
    space = make_space("booking-duty-rules")
    actor = make_user("booking-duty-rules", access_status="active", account_kind="staff", staff_makerspace=space)
    assign_builtin_roles(actor, space, "booking_manager")
    bookable = BookableSpace.objects.create(makerspace=space, name="Meeting room")
    url = reverse("admin-bookable-space-booking-rules", args=[bookable.pk])
    client = authenticated_client(actor)
    assert client.get(url).status_code == 200
    response = client.patch(url, {"booking_lead_time_minutes": 120}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["booking_lead_time_minutes"] == 120
    bookable.refresh_from_db()
    assert bookable.booking_lead_time_minutes == 120


@pytest.fixture
def handover(monkeypatch, settings):
    settings.API_CLIENT_AUTH_REQUIRED = False
    monkeypatch.setattr("apps.evidence.storage.finalize_upload",
        lambda evidence, max_bytes: EvidenceValidationResult(size=123, content_type="image/jpeg"))
    space = make_space("handover-duty")
    actor = make_handout_member("handover-duty", space)
    return space, actor, authenticated_client(actor)


def test_handover_issues_accepted_and_returns_with_evidence(handover):
    space, actor, client = handover
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    assign_scanned_box(request, make_box(space), actor)
    issue = make_issue_evidence(space, actor)
    response = client.post(issue_url(request), {"evidence_id": issue.pk, "remark": "Handed over"}, format="json")
    assert response.status_code == 200, response.data
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ISSUED
    evidence = make_return_evidence(space, actor)
    response = client.post(return_url(request), return_payload(request, evidence), format="json")
    assert response.status_code == 200, response.data
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.RETURNED
    product.refresh_from_db()
    assert product.issued_quantity == 0


def test_handover_cannot_issue_pending_review_or_make_review_decisions(handover):
    space, actor, client = handover
    product = make_product(space)
    request = make_accepted_request(space, product, 1)
    request.status = HardwareRequest.Status.PENDING_APPROVAL
    request.save(update_fields=["status"])
    assign_scanned_box(request, make_box(space), actor)
    response = client.post(issue_url(request), {
        "evidence_id": make_issue_evidence(space, actor).pk, "remark": "Still pending",
    }, format="json")
    assert response.status_code == 409, response.data
    for action in ("accept", "reject"):
        assert client.post(reverse(f"hardware_requests:request-{action}", args=[request.pk]), {}, format="json").status_code == 403
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.PENDING_APPROVAL
    product.refresh_from_db()
    assert product.issued_quantity == 0
    assert not rbac.can(actor, rbac.Action.EDIT_INVENTORY, space.pk)
    response = client.patch(f"/api/v1/admin/inventory/{product.pk}", {"name": "Changed"}, format="json")
    assert response.status_code == 404
    product.refresh_from_db()
    assert product.name != "Changed"


def test_handover_can_create_a_direct_handout(handover):
    space, actor, client = handover
    product = make_product(space)
    borrower = eligible_member(space)
    response = client.post(direct_url(space), direct_payload(
        makerspace=space, borrower=borrower, evidence_id=make_issue_evidence(space, actor).pk,
        items=[{"product_id": product.pk, "quantity": 1}],
    ), format="json")
    assert response.status_code == 201, response.data
    loan = PublicToolLoan.objects.get(makerspace=space)
    assert loan.request.status == HardwareRequest.Status.ISSUED
    product.refresh_from_db()
    assert product.issued_quantity == 1


def test_handover_collects_only_completed_machine_jobs(handover):
    space, actor, client = handover
    kind = MachineType.objects.create(makerspace=space, name="Laser", slug="handover-laser")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Laser")
    bucket = ServiceBucket.objects.create(machine=machine, name="Service")
    requester = make_user("handover-machine-borrower", access_status="active")
    rows = [MachineServiceRequest.objects.create(
        makerspace=space, assigned_machine=machine, bucket=bucket, requester=requester,
        title=status, status=status,
    ) for status in ("completed", "in_progress")]
    response = client.post(reverse("admin-machine-service-request-collect", args=[rows[0].pk]), {}, format="json")
    assert response.status_code == 200, response.data
    rows[0].refresh_from_db()
    assert rows[0].status == "collected" and rows[0].collected_by_id == actor.pk
    response = client.post(reverse("admin-machine-service-request-collect", args=[rows[1].pk]), {}, format="json")
    assert response.status_code == 404
    rows[1].refresh_from_db()
    assert rows[1].status == "in_progress"
