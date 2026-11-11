from unittest.mock import Mock

import pytest
from django.conf import settings

from apps.events.tasks_sweeps import take_ids
from apps.events.submissions.models_assets import EventProgrammeSweepCursor
from apps.events.judging.models_results import JudgingNotice
from apps.events.judging import lifecycle
from apps.operations.management.commands.run_scheduled_tasks import SCHEDULED_TASKS
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def test_every_new_worker_has_the_same_beatless_cadence_and_task():
    expected = {"event-asset-work": 1, "event-asset-deadlines": 1, "event-asset-retention": 5,
        "event-asset-obligations": 5, "event-certificate-batches": 1, "event-certificate-renders": 5,
        "event-print-cleanup": 5, "event-judging-notices": 1}
    mirror = {name: (task, minutes) for name, task, minutes in SCHEDULED_TASKS}
    for name, minutes in expected.items():
        assert mirror[name][0] == settings.CELERY_BEAT_SCHEDULE[name]["task"]
        assert mirror[name][1] == minutes


def test_circular_cursor_survives_restart_and_a_failed_first_page_does_not_starve_later_notices(monkeypatch):
    event = open_event(event_space("fair-notice-recovery"))
    notices = [JudgingNotice.objects.create(event=event, kind="results", source_id=i, revision=1) for i in range(1, 4)]
    notify = Mock(side_effect=[RuntimeError("provider down"), None, None, None])
    monkeypatch.setattr(lifecycle, "runtime", lambda: Mock(notify_intent=notify))
    assert lifecycle.sweep_notices(limit=1)["failed"] == 1
    assert EventProgrammeSweepCursor.objects.get(namespace="judging-notices").last_id == notices[0].pk
    lifecycle.sweep_notices(limit=1)
    lifecycle.sweep_notices(limit=1)
    lifecycle.sweep_notices(limit=1)
    assert [call.args[0] for call in notify.call_args_list] == [notices[0].pk, notices[1].pk, notices[2].pk, notices[0].pk]
