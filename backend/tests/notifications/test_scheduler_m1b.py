"""Member push cannot disappear in beat-less deployments or source-gate registries."""

from django.conf import settings

from apps.operations.management.commands.run_scheduled_tasks import SCHEDULED_TASKS
from apps.notifications.tasks import deliver_member_push, sweep_member_push
from apps.tenant_migration.gate_policy_tasks import FANOUT_GATE_PARTICIPANTS, TASK_INTERNAL_PARTICIPANTS
from apps.tenant_migration.source_gate_fanout_guards import validate_fanout_gate_coverage
from apps.tenant_migration.source_gate_guards import validate_task_coverage
from tests.test_scheduled_tasks import (
    test_every_beat_entry_has_a_beat_less_counterpart as assert_scheduler_parity,
    test_every_declared_task_actually_resolves as assert_scheduled_tasks_resolve,
)


def test_recovery_sweep_has_five_minute_cadence_in_both_schedulers_and_gate_registry():
    name = "member-push-recovery"
    path = "apps.notifications.tasks.sweep_member_push"
    entry = settings.CELERY_BEAT_SCHEDULE[name]
    assert entry["task"] == path
    assert entry["schedule"]._orig_minute == "*/5"
    assert entry["schedule"]._orig_hour == "*"
    assert [row for row in SCHEDULED_TASKS if row[0] == name] == [(name, path, 5)]
    assert path in TASK_INTERNAL_PARTICIPANTS
    assert path in FANOUT_GATE_PARTICIPANTS
    assert path in validate_fanout_gate_coverage()
    assert_scheduler_parity()
    assert_scheduled_tasks_resolve()


def test_delivery_and_sweep_are_registered_celery_tasks_with_source_gate_coverage():
    entries = {entry.target for entry in validate_task_coverage()}
    for task in (deliver_member_push, sweep_member_push):
        assert task.name in entries
        assert task.name in TASK_INTERNAL_PARTICIPANTS
        assert callable(task.run)
        assert task.app.tasks[task.name] is task._get_current_object()
