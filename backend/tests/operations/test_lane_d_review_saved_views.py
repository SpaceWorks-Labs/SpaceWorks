"""Missing subjects are filtered without relaxing exact-subject authorization."""

from unittest.mock import Mock

import pytest
from django.http import Http404

from apps.operations.models_saved_views import SavedView
from apps.operations.views_report_views import authorize_view
from tests.events.collab_helpers import client_for
from tests.events.lane_d_helpers import fixture
from tests.events.ticketing_helpers import open_event

pytestmark = pytest.mark.django_db


def saved(space, actor, event, name):
    return SavedView.objects.create(makerspace=space, owner=actor, entity="report", name=name,
        state={"report_key": "event-registrations", "filters": {"subject_kind": "event", "subject_id": event.pk}})


def test_deleted_draft_subject_does_not_hide_other_saved_views(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    draft = open_event(space)
    draft.status = "draft"
    draft.save(update_fields=["status"])
    stale = saved(space, actor, draft, "Deleted occurrence")
    live = saved(space, actor, event, "Live occurrence")
    draft.delete()
    with pytest.raises(Http404):
        authorize_view(actor, space, stale.state)
    base = f"/api/v1/admin/makerspaces/{space.pk}/saved-report-views"
    response = client_for(actor).get(base)
    assert response.status_code == 200, response.data
    assert response.data["count"] == 1
    assert [row["id"] for row in response.data["results"]] == [live.pk]
    assert client_for(actor).get(f"{base}/{stale.pk}").status_code == 404


def test_subject_disappearing_between_owner_and_reader_checks_is_filtered(monkeypatch):
    space, actor, user, event, registration = fixture(monkeypatch)
    draft = open_event(space)
    draft.status = "draft"
    draft.save(update_fields=["status"])
    stale = saved(space, actor, draft, "Disappearing subject")
    live = saved(space, actor, event, "Live subject")

    def delete_after_owner_check(reader, makerspace, state):
        result = authorize_view(reader, makerspace, state)
        if state == stale.state:
            draft.delete()
        return result

    authorize = Mock(side_effect=delete_after_owner_check)
    monkeypatch.setattr("apps.operations.views_report_views.authorize_view", authorize)
    response = client_for(actor).get(f"/api/v1/admin/makerspaces/{space.pk}/saved-report-views")
    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [live.pk]
    assert authorize.call_count == 4
    assert authorize.call_args_list[1].args == (actor, space, stale.state)
