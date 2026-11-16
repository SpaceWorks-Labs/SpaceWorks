"""L16 (#103, #102, C-3, Q-T2): reporting, triage, Technician scope and the lifecycle."""

from unittest.mock import patch

import pytest

from apps.audit.models import AuditLog
from apps.integrations.models import EmailLog
from apps.maintenance.models import IssueAssignment, IssueReport, WorkOrder
from apps.maintenance.repairs import services_issues as svc
from tests.maintenance.l16_helpers import in_house, loan, switch, world
from tests.return_helpers import authenticated_client, make_member, make_user

pytestmark = pytest.mark.django_db
MEMBER = "/api/v1/member/issues"


def report(client, w, request, **extra):
    body = {"makerspace_id": w.space.pk, "loan_id": request.pk, "title": "Tip is loose",
            "description": "The tip wobbles and does not heat.", **extra}
    return client.post(MEMBER, body, format="json")


def staff(user):
    return authenticated_client(user)


def test_the_borrower_reports_from_their_own_loan_and_others_are_not_eligible():
    w = world("l16-rep")
    request, borrower = loan(w)
    response = report(authenticated_client(borrower), w, request)
    assert response.status_code == 201, response.content
    issue = IssueReport.objects.get(pk=response.json()["id"])
    assert (issue.area, issue.subject_type, issue.product_id, issue.reporter_id) == (
        "inventory", "inventory_product", w.product.pk, borrower.pk)
    assert AuditLog.objects.filter(action="issue.reported", makerspace=w.space).exists()
    stranger = make_user("l16-rep-stranger", access_status="active")
    refused = report(authenticated_client(stranger), w, request)
    assert refused.status_code == 403 and refused.json()["code"] == "reporter_not_eligible"
    mine = authenticated_client(borrower).get(MEMBER).json()
    assert [row["id"] for row in mine] == [issue.pk] and "reporter_name" not in mine[0]


def test_reporting_is_off_when_its_switch_is_off_and_data_is_kept():
    w = world("l16-off")
    request, borrower = loan(w)
    assert report(authenticated_client(borrower), w, request).status_code == 201
    switch(w.space, off=("inventory.issue_reporting", "machines.issue_reporting", "bookings.issue_reporting"))
    assert report(authenticated_client(borrower), w, request).status_code == 404
    assert IssueReport.objects.filter(makerspace=w.space).count() == 1


@pytest.mark.django_db(transaction=True)  # decision 221(f): the reporter's direct mail is sent on_commit
def test_triage_with_repairs_on_opens_the_work_order_and_notify_only_does_not():
    w = world("l16-triage")
    request, borrower = loan(w)
    issue_id = report(authenticated_client(borrower), w, request).json()["id"]
    response = staff(w.manager).post(f"/api/v1/admin/issues/{issue_id}/triage", {"priority": "high"},
                                     format="json")
    assert response.status_code == 200, response.content
    issue = IssueReport.objects.get(pk=issue_id)
    assert issue.state == "triaged" and WorkOrder.objects.filter(pk=issue.work_order_id,
                                                                 subject_type="inventory_product").exists()
    switch(w.space, off=("inventory.repairs",))
    second = report(authenticated_client(borrower), w, request).json()["id"]
    staff(w.manager).post(f"/api/v1/admin/issues/{second}/triage", {}, format="json")
    assert IssueReport.objects.get(pk=second).work_order_id is None
    fixed = staff(w.manager).post(f"/api/v1/admin/issues/{second}/fix", {"resolution": "Tightened it."},
                                  format="json")
    assert fixed.status_code == 200 and fixed.json()["state"] == "fixed"
    assert [log.to_email for log in EmailLog.objects.filter(event="repair_closed")] == [borrower.email]


def test_a_technician_sees_and_works_only_assigned_jobs_and_never_the_reporters_details():
    w = world("l16-tech")
    request, borrower = loan(w)
    borrower.first_name, borrower.display_name = "Asha", "Asha Rao"
    borrower.save(update_fields=["first_name", "display_name"])
    issue_id = report(authenticated_client(borrower), w, request).json()["id"]
    issue = svc.triage(w.manager, IssueReport.objects.get(pk=issue_id))
    tech = staff(w.tech)
    assert tech.get(f"/api/v1/admin/issues/{issue_id}").status_code == 404
    assert tech.get(f"/api/v1/admin/makerspaces/{w.space.pk}/my-jobs").json()["results"] == []
    contact = in_house(w)
    svc.assign(w.manager, issue, contact=contact)
    detail = tech.get(f"/api/v1/admin/issues/{issue_id}").json()
    assert detail["viewer_role"] == "technician" and detail["reporter_name"] == "Asha"
    assert detail["reporter_email"] == "" and detail["default_contact_ids"] == []
    assert [row["id"] for row in tech.get(f"/api/v1/admin/makerspaces/{w.space.pk}/my-jobs").json()["results"]] \
        == [issue_id]
    assert tech.post(f"/api/v1/admin/issues/{issue_id}/triage", {}, format="json").status_code == 403
    assert tech.post(f"/api/v1/admin/issues/{issue_id}/start", {}, format="json").status_code == 200
    done = tech.post(f"/api/v1/admin/issues/{issue_id}/fix", {"resolution": "New tip fitted."}, format="json")
    assert done.status_code == 200 and done.json()["state"] == "fixed"
    assert WorkOrder.objects.get(pk=IssueReport.objects.get(pk=issue_id).work_order_id).status == "done"
    assert tech.post(f"/api/v1/admin/issues/{issue_id}/close", {}, format="json").status_code == 403
    manager_view = staff(w.manager).get(f"/api/v1/admin/issues/{issue_id}").json()
    assert manager_view["reporter_name"] == "Asha Rao" and manager_view["viewer_role"] == "manager"


def test_machine_issues_follow_the_machine_type_scope_of_a_machine_manager():
    from apps.machines.models_membership_scope import MembershipMachineTypeScope
    from apps.makerspaces.models import MakerspaceMembership
    w = world("l16-scope")
    other_manager = make_member("l16-scope-mm", w.space, membership_role="machine_manager")
    membership = MakerspaceMembership.staff_tracks.get(user=other_manager, makerspace=w.space)
    MembershipMachineTypeScope.objects.create(membership=membership, machine_type=w.other_kind)
    issue = svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.machine, title="Lens cracked")
    client = staff(other_manager)
    assert client.get(f"/api/v1/admin/issues/{issue.pk}").status_code == 404
    opened = client.post(f"/api/v1/admin/makerspaces/{w.space.pk}/issues",
                         {"subject_type": "machine", "subject_id": w.machine.pk, "title": "x"}, format="json")
    assert opened.status_code == 403 and opened.json()["code"] == "out_of_scope"
    assert client.post(f"/api/v1/admin/makerspaces/{w.space.pk}/issues",
                       {"subject_type": "machine", "subject_id": w.other.pk, "title": "Belt"},
                       format="json").status_code == 201


def test_a_manager_self_assigns_and_staff_list_is_paginated():
    w = world("l16-self")
    issue = svc.open_issue(w.manager, w.space, subject_type="bookable_space", subject=w.room, title="Leak")
    response = staff(w.manager).post(f"/api/v1/admin/issues/{issue.pk}/assign", {"myself": True}, format="json")
    assert response.status_code == 200 and response.json()["state"] == "assigned"
    assert IssueAssignment.objects.filter(issue=issue, person=w.manager).exists()
    listing = staff(w.manager).get(f"/api/v1/admin/makerspaces/{w.space.pk}/issues?assigned=me").json()
    assert listing["count"] == 1 and listing["results"][0]["id"] == issue.pk


def cool():
    from datetime import timedelta
    from django.utils import timezone
    from apps.accounts.models import EmailVerificationChallenge
    EmailVerificationChallenge.objects.update(last_sent_at=timezone.now() - timedelta(minutes=5))


def test_account_less_borrower_reports_with_a_verified_email():
    from apps.hardware_requests.contact_verification import email_key, issue_code
    from apps.hardware_requests.models import HardwareRequest
    w = world("l16-anon")
    w.space.enabled_modules = [key for key in w.space.enabled_modules if key not in ("member_accounts", "membership")]
    w.space.save(update_fields=["enabled_modules"])
    request, _ = loan(w)
    HardwareRequest.objects.filter(pk=request.pk).update(
        anonymous_payload_fingerprint=email_key(w.space, "pat@example.test"))
    sent = []
    with patch("apps.integrations.email.send_email_verification_otp", lambda to, code: sent.append(code) or True):
        issue_code(w.space, "pat@example.test")
    url = f"/api/v1/public/{w.space.slug}/issues"
    body = {"loan_id": request.pk, "title": "Broken", "description": "Cracked case.", "contact_name": "Pat Lee",
            "contact_email": "pat@example.test", "email_code": "000000"}
    from rest_framework.test import APIClient
    assert APIClient().post(url, body, format="json").status_code == 400  # wrong code
    cool()
    with patch("apps.integrations.email.send_email_verification_otp", lambda to, code: sent.append(code) or True):
        issue_code(w.space, "pat@example.test")
    ok = APIClient().post(url, {**body, "email_code": sent[-1]}, format="json")
    assert ok.status_code == 201, ok.content
    issue = IssueReport.objects.get(pk=ok.json()["id"])
    assert issue.reporter_id is None and issue.reporter_email == "pat@example.test"
    with patch("apps.integrations.email.send_email_verification_otp", lambda to, code: sent.append(code) or True):
        issue_code(w.space, "sam@example.test")
    wrong = APIClient().post(url, {**body, "contact_email": "sam@example.test", "email_code": sent[-1]},
                             format="json")
    assert wrong.status_code == 403 and wrong.json()["code"] == "reporter_not_eligible"


def test_a_technician_fixing_a_machine_repair_writes_the_machine_maintenance_log():
    from apps.maintenance.models import MaintenanceLog
    w = world("l16-machine-fix")
    issue = svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.machine, title="Belt slips")
    svc.assign(w.manager, issue, contact=in_house(w))
    tech = staff(w.tech)
    assert tech.post(f"/api/v1/admin/issues/{issue.pk}/start", {}, format="json").status_code == 200
    assert tech.post(f"/api/v1/admin/issues/{issue.pk}/fix", {"resolution": "Belt tensioned."},
                     format="json").status_code == 200
    order = WorkOrder.objects.get(pk=IssueReport.objects.get(pk=issue.pk).work_order_id)
    assert order.status == "done" and MaintenanceLog.objects.filter(pk=order.log_id, performed_by=w.tech).exists()
    other = svc.open_issue(w.manager, w.space, subject_type="machine", subject=w.other, title="Spindle")
    assert tech.post(f"/api/v1/admin/issues/{other.pk}/start", {}, format="json").status_code == 404


def test_reject_needs_a_reason_and_cancels_the_work_order():
    w = world("l16-reject")
    issue = svc.open_issue(w.manager, w.space, subject_type="bookable_space", subject=w.room, title="Door")
    client = staff(w.manager)
    assert client.post(f"/api/v1/admin/issues/{issue.pk}/reject", {"reason": ""}, format="json").status_code == 400
    assert client.post(f"/api/v1/admin/issues/{issue.pk}/reject", {"reason": "Duplicate"},
                       format="json").json()["state"] == "rejected"
    assert WorkOrder.objects.get(pk=IssueReport.objects.get(pk=issue.pk).work_order_id).status == "cancelled"
