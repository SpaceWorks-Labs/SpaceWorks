"""Decision 246 (lane T4): service-level conditions for the `issue_reported` staff notice (221c/221f).

Calls `repairs.notify.staff` and `notify.eligible` directly after one real report: recipients are
staff of the report's own space only, a replay reserves the same intent (no duplicate), and the
queued notice goes stale when the area's issue-reporting switch is turned off or the issue closes.
"""
import pytest

from apps.integrations.models_contract import NotificationEnvelope
from apps.maintenance.models import IssueReport
from apps.maintenance.repairs import notify
from tests.maintenance.l16_helpers import loan, switch, world
from tests.maintenance.test_l16_issues import report
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db(transaction=True)


def reported(slug):
    w = world(slug)
    request, borrower = loan(w)
    response = report(authenticated_client(borrower), w, request)
    assert response.status_code == 201, response.content
    return w, IssueReport.objects.get(pk=response.json()["id"])


def rows(issue):
    return NotificationEnvelope.objects.filter(event="issue_reported", source_id=str(issue.pk))


def test_issue_reported_goes_to_this_spaces_staff_and_never_the_reporter_or_another_space():
    w, issue = reported("t246-issue")
    other = world("t246-issue-other")
    heard = set(rows(issue).values_list("recipient_id", flat=True))
    assert w.manager.pk in heard
    assert issue.reporter_id not in heard
    assert other.manager.pk not in heard
    assert set(rows(issue).values_list("makerspace_id", flat=True)) <= {w.space.pk}
    assert set(rows(issue).values_list("audience", flat=True)) <= {"staff"}


def test_replaying_the_notice_reserves_the_same_intent():
    _w, issue = reported("t246-issue-replay")
    before = rows(issue).count()
    assert before > 0
    notify.staff(issue, "issue_reported")
    notify.staff(issue, "issue_reported")
    assert rows(issue).count() == before


def test_a_member_without_staff_authority_hears_nothing():
    w, issue = reported("t246-issue-plain")
    plain = make_member("t246-issue-plain-m", w.space, membership_role="member")
    notify.staff(issue, "issue_reported")
    assert plain.pk not in set(rows(issue).values_list("recipient_id", flat=True))


def test_the_queued_notice_is_stale_when_the_area_is_off_or_the_issue_is_closed():
    w, issue = reported("t246-issue-stale")
    envelope = rows(issue).filter(recipient=w.manager).get()
    assert notify.eligible(envelope)
    IssueReport.objects.filter(pk=issue.pk).update(state="fixed")
    assert not notify.eligible(envelope)
    IssueReport.objects.filter(pk=issue.pk).update(state=IssueReport.OPEN_STATES[0])
    fresh = IssueReport.objects.get(pk=issue.pk)
    envelope.revision = notify.version(fresh, "issue_reported")
    assert notify.eligible(envelope)
    switch(w.space, off=("inventory.issue_reporting",))
    assert not notify.eligible(envelope)
