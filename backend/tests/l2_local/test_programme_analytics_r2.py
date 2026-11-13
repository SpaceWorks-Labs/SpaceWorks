"""G8 analytics extras: counts only, free text never charted, k >= 10 suppression for orgs."""
import json

import pytest

from apps.events.models import EventFeedbackResponse, EventFeedbackSurvey
from apps.events.programme.analytics_extras import answer_charts, extras
from apps.events.programme.analytics_org import K, _suppress
from apps.events.services_registration import register
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event

pytestmark = pytest.mark.django_db
QUESTIONS = [
    {"id": "q1", "label": "Venue", "type": "single_choice", "options": ["Good", "Bad"], "required": False},
    {"id": "q2", "label": "Comments", "type": "paragraph", "options": [], "required": False},
]


def test_choice_counts_only_and_free_text_is_never_charted():
    space = event_space("charts")
    event = open_event(space)
    survey = EventFeedbackSurvey.objects.create(event=event, title="How was it", questions=QUESTIONS,
                                                anonymous=True)
    for choice in ("Good", "Good", "Bad", "Sneaky"):
        EventFeedbackResponse.objects.create(survey=survey, answers_snapshot=json.dumps({"version": 1, "answers": [
            {"id": "q1", "label": "Venue", "type": "single_choice", "value": choice},
            {"id": "q2", "label": "Comments", "type": "paragraph", "value": "my phone is 555"}]}))
    charts = answer_charts(event)
    assert [chart["question_id"] for chart in charts] == ["q1"]
    assert charts[0]["answers"] == [{"label": "Good", "count": 2}, {"label": "Bad", "count": 1}]
    assert "555" not in json.dumps(charts, default=str)


def test_extras_endpoint_shapes_and_short_links_null_while_off():
    space = event_space("extras")
    staff = make_staff(space)
    event = open_event(space)
    member = account("extras-member")
    register(event, member=member, actor=member)
    data = extras(event)
    assert data["short_link_visits"] is None
    assert data["waitlist"] == {"ever_waitlisted": 0, "promoted": 0, "still_waiting": 0, "conversion_percent": None}
    response = client_for(staff).get(f"/api/v1/admin/events/{event.pk}/analytics/extras/")
    assert response.status_code == 200
    assert set(response.json()) >= {"arrivals", "checkin_methods", "answers", "waitlist", "series", "short_link_visits"}


def test_small_organisation_counts_are_suppressed():
    assert K == 10
    assert _suppress(9) is None and _suppress(10) == 10
