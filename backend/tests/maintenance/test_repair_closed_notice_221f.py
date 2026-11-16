"""Decision 221(f): the reporter's repair-closed notice goes through the notification pipeline.

An account reporter gets an envelope (their preferences and quiet hours apply) and keeps the one
direct email unless their own channel already emails it; the notice is stale if the issue is no
longer fixed or closed, and silent once the area's reporting and repairs switches are off.
"""
import pytest

from apps.integrations.models_contract import NotificationEnvelope
from apps.maintenance.models import IssueReport
from apps.maintenance.repairs.repair_closed_notices import eligible
from tests.maintenance.l16_helpers import loan, switch, world
from tests.maintenance.test_l16_issues import report, staff
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def fixed_issue(slug):
    w = world(slug)
    request, borrower = loan(w)
    issue_id = report(authenticated_client(borrower), w, request).json()["id"]
    staff(w.manager).post(f"/api/v1/admin/issues/{issue_id}/triage", {}, format="json")
    response = staff(w.manager).post(f"/api/v1/admin/issues/{issue_id}/fix", {"resolution": "Tightened it."},
                                     format="json")
    assert response.status_code == 200, response.content
    return w, borrower, IssueReport.objects.get(pk=issue_id)


def test_an_account_reporter_gets_a_repair_closed_envelope_naming_no_staff_note():
    w, borrower, issue = fixed_issue("n221-rc")
    rows = list(NotificationEnvelope.objects.filter(event="repair_closed", source_id=str(issue.pk)))
    assert [(row.recipient_id, row.audience, row.feature) for row in rows] == [
        (borrower.pk, "requester", "hardware_requests")]
    assert "Tightened it." not in rows[0].message_body  # the resolution note is staff-facing
    assert eligible(rows[0])


def test_the_notice_is_stale_when_the_issue_is_reopened_or_the_area_is_switched_off():
    w, _borrower, issue = fixed_issue("n221-rc-stale")
    envelope = NotificationEnvelope.objects.get(event="repair_closed", source_id=str(issue.pk))
    assert eligible(envelope)
    IssueReport.objects.filter(pk=issue.pk).update(state="in_progress")
    assert not eligible(envelope)
    IssueReport.objects.filter(pk=issue.pk).update(state="fixed")
    switch(w.space, off=("inventory.issue_reporting", "inventory.repairs"))
    assert not eligible(envelope)
