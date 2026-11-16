"""Decision 301 review (FIX-HACK): hackathons-off 404s, declining a join request, team notices.

Not run by the author; stubs the seams so no database fixtures are needed.
"""
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import APIException

from apps.events.hackathons import api_base, team_notifications
from apps.events.hackathons.admission_errors import ProgrammeError


def _view(monkeypatch, enabled):
    event = SimpleNamespace(makerspace=object())
    monkeypatch.setattr(api_base.ProgrammeView, "member_target", lambda self, r, m, pk: (event, "config"))
    monkeypatch.setattr(api_base, "hackathon_enabled", lambda space: enabled)
    return api_base.ProgrammeView()


def test_team_routes_answer_404_when_the_hackathons_switch_is_off(monkeypatch):
    with pytest.raises(ProgrammeError) as caught:
        _view(monkeypatch, False).team_target(None, 1, 2)
    assert caught.value.status_code == 404


def test_team_routes_work_when_the_switch_is_on(monkeypatch):
    assert _view(monkeypatch, True).team_target(None, 1, 2)[1] == "config"


def test_submission_routes_answer_404_when_the_hackathons_switch_is_off(monkeypatch):
    from apps.events.submissions import views_base
    from apps.events.submissions.errors import SubmissionError
    event = SimpleNamespace(makerspace_id=1, makerspace=object())
    monkeypatch.setattr("apps.events.models.Event.objects",
                        SimpleNamespace(select_related=lambda *a: SimpleNamespace(filter=lambda **kw: SimpleNamespace(first=lambda: event))))
    monkeypatch.setattr("apps.makerspaces.platform.feature_enabled", lambda space, key: False)
    view = views_base.PrivateSubmissionView()
    monkeypatch.setattr(views_base.APIView, "initial", lambda self, request, *a, **kw: None)
    with pytest.raises(SubmissionError):
        view.initial(SimpleNamespace(method="GET", data={}), makerspace_id=1, pk=2)


def test_decline_is_a_member_route_the_leader_gets_and_others_do_not(monkeypatch):
    from django.urls import reverse
    from apps.events.hackathons import team_projection
    monkeypatch.setattr(team_projection, "profile", lambda event_id, member_id: None)
    monkeypatch.setattr("apps.makerspaces.platform.feature_enabled", lambda space, key: False)

    def team():
        members = [SimpleNamespace(pk=1, member_id=10, joined_at=None), SimpleNamespace(pk=2, member_id=11, joined_at=None)]
        class Rows(list):
            def order_by(self, *a):
                return self
        rows = SimpleNamespace(filter=lambda **kw: Rows(members if kw.get("state") == "active" else []))
        return SimpleNamespace(pk=3, event_id=2, version=4, state="forming", name="T", leader_id=10, seeking_members=True,
                               finder_intro="", skills=[], eligibility_issue=False, roster_hash="", memberships=rows,
                               event=SimpleNamespace(makerspace=object()))

    config = SimpleNamespace(team_mode="individual_then_team")
    leader = team_projection.project_team(team(), actor=SimpleNamespace(pk=10), config=config)
    assert "decline" in leader["allowed_actions"] and "accept" in leader["allowed_actions"]
    member = team_projection.project_team(team(), actor=SimpleNamespace(pk=11), config=config)
    assert "decline" not in member["allowed_actions"]
    url = reverse("events-programme-member-team-decline-request", kwargs={"makerspace_id": 1, "pk": 2, "team_id": 3})
    assert url.endswith("/teams/3/decline-request/")


def test_the_decline_route_is_classified_for_native_clients():
    from apps.accounts.programme_route_catalog_parity_eb3 import EB3_ROUTES
    assert ("events-programme-member-team-decline-request", ("POST",), "event") in EB3_ROUTES


def test_decline_input_needs_a_request_id():
    from apps.events.hackathons.serializers_commands import DeclineRequestInput
    base = {"operation_id": "6f0c2d2e-0f4c-4a5b-9c1e-0a1b2c3d4e5f", "expected_version": 1}
    assert not DeclineRequestInput(data=base).is_valid()
    assert DeclineRequestInput(data={**base, "request_id": 5}).is_valid()


def test_team_notices_are_registered_in_the_catalogue():
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    from apps.integrations.notification_enums import NotificationFeature as F
    for kind in team_notifications.MESSAGES:
        assert kind in FEATURE_EVENTS[F.EVENTS], kind
    assert "team_invited" in FEATURE_EVENTS[F.EVENTS]
    assert "team_join_declined" in team_notifications.MESSAGES


def test_a_notice_captures_recipients_and_version_when_the_decision_is_made(monkeypatch):
    seen = {}
    monkeypatch.setattr(team_notifications, "deliver_team_notice",
                        lambda team, kind, members, version, request_id=None: seen.update(
                            members=members, version=version, request_id=request_id))
    team = SimpleNamespace(version=9, memberships=SimpleNamespace(
        filter=lambda **kw: SimpleNamespace(values_list=lambda *a, **k: iter([4, 5]))))
    team_notifications.emit_team_locked(team=team, kind="team_join_declined", member_ids=(4,), request_id=21)
    assert seen == {"members": [4], "version": 9, "request_id": 21}
    team_notifications.emit_team_locked(team=team, kind="team_membership_updated")
    assert seen["members"] == [4, 5] and seen["version"] == 9


def test_unknown_team_notice_is_refused():
    with pytest.raises(ValueError):
        team_notifications.emit_team_locked(team=SimpleNamespace(version=1), kind="nope")


@pytest.mark.django_db
def test_a_notice_survives_later_team_changes():
    """team_eligible no longer compares the team version, so a bump after the decision keeps the notice."""
    import inspect
    source = inspect.getsource(team_notifications.team_eligible)
    assert "team.version" not in source and "envelope.revision" not in source
