"""Decision 221b/f: lending notices of an event-linked loan say "for <event>"; other loans are unchanged."""
import pytest

from apps.hardware_requests.loan_event_notice import annotate, loan_event
from apps.hardware_requests.notifications_loans import notify_renewed
from apps.integrations.models_contract import NotificationEnvelope
from tests.events.test_event_equipment_desk import _enable, _event, _link
from tests.hardware_requests.loan_policy_helpers import setup_loan

pytestmark = pytest.mark.django_db(transaction=True)


def renewed_rows():
    return list(NotificationEnvelope.objects.filter(feature="hardware_requests", event="renewed").order_by("pk"))


def test_an_event_linked_loan_notice_names_the_event():
    space, _member, _m, _p, loan, _policy, _client = setup_loan("n221b-evt", linked=False)
    _enable(space)
    event = _event(space)
    _link(space, loan, event)
    found = loan_event(loan)  # decision 221b/f: id and title plus the schedule and desk link the notice carries
    assert (found["id"], found["title"]) == (event.pk, event.title)
    assert found["desk_link"] == f"/admin/events/{event.pk}"
    assert found["starts_at"] and found["ends_at"]
    notify_renewed(loan, by_staff=False)
    rows = renewed_rows()
    assert rows and all(event.title in row.message_body for row in rows)
    assert all(row.context["event_id"] == event.pk for row in rows)


def test_a_loan_without_an_event_is_unchanged():
    space, _member, _m, _p, loan, _policy, _client = setup_loan("n221b-plain", linked=False)
    _enable(space)
    assert loan_event(loan) is None
    notify_renewed(loan, by_staff=False)
    assert all("For event" not in row.message_body and "event_id" not in row.context for row in renewed_rows())


def test_the_event_context_is_silent_when_events_is_off_or_the_link_is_inactive():
    space, _member, _m, _p, loan, _policy, _client = setup_loan("n221b-off", linked=False)
    _enable(space)
    link = _link(space, loan, _event(space))
    assert loan_event(loan)
    type(link).objects.filter(pk=link.pk).update(active=False, event=None)
    assert loan_event(loan) is None


def test_annotate_adds_subject_and_text_and_leaves_none_alone():
    out = annotate({"subject": "Due soon", "text": "Return it.", "html": "<p>x</p>"}, {"id": 1, "title": "Expo <b>"})
    assert out["subject"] == "Due soon (for Expo <b>)" and out["text"].endswith("For event: Expo <b>")
    assert "&lt;b&gt;" in out["html"]
    assert annotate(None, {"id": 1, "title": "x"}) is None
    original = {"subject": "s", "text": "t"}
    assert annotate(original, None) is original
