"""Regressions for the ETA review-1 P3 follow-ups (lock modes, submit order, scope recheck, stats)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.inventory.serializers import PublicStatsStatusCountsSerializer
from apps.machines.models import MachineServiceRequest, MachineType
from apps.machines.service_workflow import cancel
from apps.machines.service_workflow_cancel import CancelRefused
from apps.makerspaces import guards, limits_usage
from tests.account_split_g2_helpers import staff_for_actions
from tests.machines.eta_helpers import job, world

pytestmark = pytest.mark.django_db


def test_staff_whose_machine_scope_does_not_cover_the_job_is_refused_under_the_lock():
    w = world("followup-scope")
    other = MachineType.objects.create(makerspace=w.space, slug="followup-other", name="Other")
    narrowed = staff_for_actions(w.space, "followup-narrowed", [Action.MANAGE_MACHINES], machine_types=[other])[0]
    row = job(w)
    with pytest.raises(CancelRefused):
        cancel(row, narrowed)
    row.refresh_from_db()
    assert row.status == MachineServiceRequest.Status.PENDING and row.cancelled_at is None
    assert not AuditLog.objects.filter(action="machine_service.cancelled").exists()
    # The same role scoped to the job's type may cancel it.
    allowed = staff_for_actions(w.space, "followup-allowed", [Action.MANAGE_MACHINES], machine_types=[w.kind])[0]
    assert cancel(row, allowed).status == MachineServiceRequest.Status.CANCELLED


def test_pooled_submit_takes_the_makerspace_fence_before_the_queue_lock():
    w = world("followup-submit-order")
    with CaptureQueriesContext(connection) as ctx:
        job(w)
    locks = [q["sql"] for q in ctx.captured_queries if " FOR " in q["sql"]]
    space = next(i for i, sql in enumerate(locks) if 'FROM "makerspaces_makerspace"' in sql)
    queue = next(i for i, sql in enumerate(locks) if 'FROM "machines_servicequeue"' in sql)
    assert space < queue
    assert all("FOR UPDATE" not in sql or "FOR NO KEY UPDATE" in sql
               for sql in locks if 'FROM "makerspaces_makerspace"' in sql)


def test_quota_and_feature_fences_take_no_key_update(monkeypatch):
    from apps.makerspaces import limits
    monkeypatch.setattr(limits, "resource_limit", lambda makerspace, key: 100)
    w = world("followup-fence")
    with CaptureQueriesContext(connection) as ctx:
        limits_usage.check_quota(w.space, "machine_service_open", adding=1)
        try:
            guards.require_feature_locked(w.space, "machines.material_catalogue")
        except Exception:
            pass
    locks = [q["sql"] for q in ctx.captured_queries if 'FROM "makerspaces_makerspace"' in q["sql"] and " FOR " in q["sql"]]
    assert len(locks) == 2 and all("FOR NO KEY UPDATE" in sql for sql in locks)


def test_public_stats_serializer_keeps_the_cancelled_count():
    data = PublicStatsStatusCountsSerializer({
        "pending": 1, "accepted": 0, "printing": 0, "completed": 0, "collected": 0,
        "failed": 0, "rejected": 0, "cancelled": 2,
    }).data
    assert data["cancelled"] == 2
