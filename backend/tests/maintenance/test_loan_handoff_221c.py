"""Decision 221(c): a damaged-return handoff notifies like a reported issue, tells the borrower, and admits reviewers."""
import pytest

from apps.maintenance.models import IssueReport
from apps.maintenance.repairs import notify, services_issues as issues
from tests.maintenance.l16_helpers import world
from tests.maintenance.test_loan_repair_handoff import damaged_return, hand_off, url, quiet_storage  # noqa: F401
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def test_handoff_raises_the_issue_reported_staff_notice_once(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "staff", lambda issue, event: calls.append((issue.pk, event)))
    w = world("c221-notice")
    request, line, _ = damaged_return(w)
    first = hand_off(w.im, w, request, line)
    assert first.status_code == 201
    assert calls == [(first.json()["issue_id"], "issue_reported")]
    hand_off(w.im, w, request, line)  # idempotent replay must not alert again
    assert len(calls) == 1


def test_request_reviewer_may_hand_off_but_sees_no_repair_detail():
    w = world("c221-reviewer")
    from tests.rbac_f6_helpers import custom_actor  # a custom role holding accept_request only
    reviewer = custom_actor(w.space, ["accept_request"], name="c221-reviewer")
    request, line, _ = damaged_return(w)
    response = hand_off(reviewer, w, request, line)
    assert response.status_code == 201, response.content
    assert response.json()["line"]["issue"] is None and response.json()["line"]["handed_off"] is True
    listed = authenticated_client(reviewer).get(url(w, request)).json()["lines"][0]
    assert listed["handed_off"] is True and listed["issue"] is None
    assert IssueReport.objects.get(return_line=line).work_order_id is not None


def _borrower_envelopes(issue):
    from apps.integrations.models_contract import NotificationEnvelope
    return list(NotificationEnvelope.objects.filter(source_kind="maintenance.repair_borrower",
                                                    source_id=str(issue.pk)))


def test_borrower_is_told_when_the_linked_repair_is_fixed():
    w = world("c221-borrower")
    request, line, _ = damaged_return(w)
    issue = IssueReport.objects.get(pk=hand_off(w.im, w, request, line).json()["issue_id"])
    issues.fix(w.manager, issue, resolution="Replaced the tip.")
    rows = _borrower_envelopes(issue)  # through the pipeline: preferences and quiet hours apply
    assert [(row.recipient_id, row.audience, row.context["outcome"]) for row in rows] == [
        (request.requester_id, "requester", "fixed")]
    assert "Replaced the tip." not in rows[0].message_body  # the resolution note is staff-facing
    issue.refresh_from_db()
    assert issue.reporter_notified_at is not None


def test_borrower_is_told_when_the_repair_is_rejected():
    w = world("c221-reject")
    request, line, _ = damaged_return(w)
    issue = IssueReport.objects.get(pk=hand_off(w.im, w, request, line).json()["issue_id"])
    issues.reject(w.manager, issue, reason="Not worth repairing.")
    rows = _borrower_envelopes(issue)
    assert [row.context["outcome"] for row in rows] == ["rejected"]
    assert "Not worth repairing." not in rows[0].message_body


def test_borrower_notice_is_stale_once_the_issue_leaves_its_outcome_state():
    from apps.maintenance.repairs.loan_borrower_notices import eligible
    w = world("c221-stale")
    request, line, _ = damaged_return(w)
    issue = IssueReport.objects.get(pk=hand_off(w.im, w, request, line).json()["issue_id"])
    issues.reject(w.manager, issue, reason="Not worth repairing.")
    envelope = _borrower_envelopes(issue)[0]
    assert eligible(envelope)
    IssueReport.objects.filter(pk=issue.pk).update(state="in_progress")
    assert not eligible(envelope)


def test_no_second_notice_when_the_borrower_is_also_the_reporter():
    from apps.maintenance.repairs.loan_borrower_notices import notify_borrower
    w = world("c221-same")
    request, line, _ = damaged_return(w)
    issue = IssueReport.objects.get(pk=hand_off(w.im, w, request, line).json()["issue_id"])
    IssueReport.objects.filter(pk=issue.pk).update(reporter=request.requester, state="fixed")
    issue.refresh_from_db()
    assert notify_borrower(issue, "fixed") is None  # the reporter's own repair_closed notice covers them
    assert _borrower_envelopes(issue) == []
