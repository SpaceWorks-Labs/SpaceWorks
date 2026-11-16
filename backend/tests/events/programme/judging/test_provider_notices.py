"""Personal judging envelopes are bound to exact live source generations."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from apps.events.judging import provider_notices as notices


@pytest.mark.parametrize("state,version,active,expected", [
    ("invalidated", 4, True, (17,)), ("assigned", 4, True, ()),
    ("invalidated", 4, False, ()), ("invalidated", 5, True, ()),
])
def test_invalidation_notice_needs_current_version_and_live_judge(monkeypatch, state, version, active, expected):
    row = SimpleNamespace(kind="assignment_invalidated", event_id=42, source_id=81, revision=4)
    assignment = SimpleNamespace(state=state, judge_role_assignment_id=9) if version == row.revision else None
    model = Mock()
    model.objects.select_related.return_value.filter.return_value.first.return_value = assignment
    ports = Mock()
    ports.judge.return_value = SimpleNamespace(active=active, event_id=42, member_id=17)
    monkeypatch.setattr(notices, "JudgeAssignment", model)
    monkeypatch.setattr(notices, "runtime", lambda: ports)
    assert notices.assignment_recipients(row) == expected
    model.objects.select_related.return_value.filter.assert_called_once_with(
        pk=81, event_id=42, version=4, round__event_id=42)


def test_assigned_notice_refuses_conflicted_or_superseded_work(monkeypatch):
    from apps.events.judging import conflicts
    row = SimpleNamespace(kind="judge_assigned", event_id=42, source_id=81, revision=1)
    assignment = SimpleNamespace(state="assigned", judge_role_assignment_id=9,
        submission_snapshot_id=100, round=SimpleNamespace(state="open"))
    model, ports = Mock(), Mock()
    model.objects.select_related.return_value.filter.return_value.first.return_value = assignment
    ports.judge.return_value = SimpleNamespace(active=True, event_id=42, member_id=17)
    monkeypatch.setattr(notices, "JudgeAssignment", model)
    monkeypatch.setattr(notices, "runtime", lambda: ports)
    eligibility = Mock(return_value=False)
    monkeypatch.setattr(conflicts, "eligible", eligibility)
    assert notices.assignment_recipients(row) == ()
    eligibility.return_value = True
    assert notices.assignment_recipients(row) == (17,)
    assignment.round.state = "closed"
    assert notices.assignment_recipients(row) == ()


def test_disabled_volunteering_suppresses_withdrawal_notices(monkeypatch):
    from apps.events.contributions.runtime_notices import contribution_recipients
    from apps.makerspaces import platform, servability
    monkeypatch.setattr(servability, "is_servable", lambda _: True)
    monkeypatch.setattr(platform, "module_enabled", lambda *args: True)
    monkeypatch.setattr(platform, "feature_enabled", lambda *args: False)
    row = SimpleNamespace(event=SimpleNamespace(makerspace=object()), signup_id=9, kind="cancelled",
        generation=2, signup=SimpleNamespace(member_id=17, state="withdrawn",
            shift=SimpleNamespace(version=2)))
    assert contribution_recipients(row) == ()
