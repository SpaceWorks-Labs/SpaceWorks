"""Decision 223 (k): the join follow-up sweep rides the hourly membership task inside the tenant boundary."""
import pytest
from django.conf import settings

from apps.events import join_followup
from apps.makerspaces.models import CommunityPolicy
from apps.operations.cloud_jobs.task_sources import TASK_SOURCES as SOURCES
from apps.tenant_migration import gate_policy_r2_l12
from tests.events.test_join_funnel_223 import _attended, _world
from tests.makerspaces.test_membership_j1 import user

pytestmark = pytest.mark.django_db(transaction=True)
SWEEP = "apps.events.join_followup.send_join_followups"
TASK = "apps.makerspaces.tasks_membership.run_membership_renewals_task"


def test_no_new_beat_entry_and_the_task_runs_the_followup_sweep(monkeypatch):
    tasks = [entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()]
    assert tasks.count(TASK) == 1 and not any("join_followup" in task for task in tasks)
    calls = []
    monkeypatch.setattr(join_followup, "send_join_followups", lambda *a, **k: calls.append(1) or 0)
    from apps.makerspaces.tasks_membership import run_membership_renewals_task
    run_membership_renewals_task()
    assert calls == [1]


def test_a_failing_followup_sweep_does_not_hide_the_renewal_result(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("mail down")
    monkeypatch.setattr(join_followup, "send_join_followups", boom)
    from apps.makerspaces.tasks_membership import run_membership_renewals_task
    run_membership_renewals_task()  # does not raise


def test_the_sweep_is_declared_in_the_gate_policy_and_the_cloud_job_sources():
    assert SWEEP in gate_policy_r2_l12.FANOUT
    assert "join_funnel" in str(SOURCES[TASK])


def test_the_sweep_sends_through_the_tenant_boundary(monkeypatch):
    makerspace = _world("jfs-boundary")
    CommunityPolicy.objects.create(makerspace=makerspace, join_followup_enabled=True, join_followup_delay_hours=24)
    visitor = user("jfs-visitor")
    _attended(makerspace, visitor, ended_hours_ago=30)
    sent = []
    monkeypatch.setattr(join_followup, "notify_join_followup", lambda row: sent.append(row.member_id))
    assert join_followup.send_join_followups() == 1 and sent == [visitor.pk]
