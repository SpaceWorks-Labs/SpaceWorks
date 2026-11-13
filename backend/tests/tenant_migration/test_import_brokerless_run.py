"""Persist the run requester at the HTTP boundary; execute from cron in eager mode."""

from datetime import timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.tenant_migration import import_job_cleanup as cleanup, services_import_run, tasks
from apps.tenant_migration.models import TenantImportJob
from apps.tenant_migration.services_import_job import claim_import_job, scrub_terminal_job
from tests.tenant_migration.protocol_helpers import superadmin
from tests.tenant_migration.test_import_async_staging import actor, client_for, ops_dir, pending_job

pytestmark = pytest.mark.django_db
IDENTITY = {"name": "Moved Lab", "slug": "moved-lab"}


@pytest.fixture
def requester():
    return superadmin("run-requester")


@pytest.fixture
def ready_job(pending_job):
    return pending_job(status=TenantImportJob.Status.READY)


def request_run(requester, job):
    return client_for(requester).post(
        reverse("tenant-migration-import-run", args=(job.pk,)),
        {"target_identity": IDENTITY}, format="json",
    )


def test_eager_view_persists_requester_and_identity_without_executing(
    actor, requester, ready_job, settings, monkeypatch,
):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    dispatch, run = Mock(), Mock()
    monkeypatch.setattr(tasks.run_import_job_task, "delay", dispatch)
    monkeypatch.setattr(services_import_run, "run_import_job", run)
    response = request_run(requester, ready_job)
    assert response.status_code == 202
    assert response.data["status"] == "materializing"
    ready_job.refresh_from_db()
    assert ready_job.actor_id == actor.pk != requester.pk
    assert ready_job.run_request == {"actor_id": requester.pk, "target_identity": IDENTITY}
    assert ready_job.run_attempt is None
    assert AuditLog.objects.get(action="tenant_migration.import_run_requested").actor_id == requester.pk
    dispatch.assert_not_called()
    run.assert_not_called()


def test_eager_sweep_dispatches_stored_requester_and_identity(
    requester, ready_job, settings, monkeypatch,
):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    claim_import_job(actor=requester, job=ready_job, target_identity=IDENTITY)
    run = Mock(return_value=ready_job)
    monkeypatch.setattr(tasks, "run_import_job", run)
    # Execute the task body at the scheduler boundary without depending on
    # Celery's cached eager configuration; its argument forwarding stays real.
    monkeypatch.setattr(tasks.run_import_job_task, "delay", tasks.run_import_job_task.run)
    # A freshly claimed run is inside the grace window; afterwards the sweep runs it.
    assert cleanup.resume_stalled_materializations() == 0
    run.assert_not_called()
    assert cleanup.resume_stalled_materializations(now=timezone.now() + timedelta(minutes=6)) == 1
    run.assert_called_once_with(str(ready_job.pk), actor_id=requester.pk, target_identity=IDENTITY)


def test_broker_sweep_recovers_a_run_whose_lock_was_lost(requester, ready_job, settings, monkeypatch):
    # With a broker, a run that lost its lock connection before commit is left
    # MATERIALIZING with a free lock; the sweep must re-dispatch it.
    settings.CELERY_TASK_ALWAYS_EAGER = False
    claim_import_job(actor=requester, job=ready_job, target_identity=IDENTITY)
    dispatch = Mock()
    monkeypatch.setattr(tasks.run_import_job_task, "delay", dispatch)
    assert cleanup.resume_stalled_materializations(now=timezone.now() + timedelta(minutes=3)) == 1
    dispatch.assert_called_once_with(str(ready_job.pk), requester.pk, IDENTITY)


def test_sweep_skips_a_run_whose_lock_is_held(requester, ready_job, settings, monkeypatch):
    from apps.tenant_migration.import_run_lock import import_run_lock

    settings.CELERY_TASK_ALWAYS_EAGER = False
    claim_import_job(actor=requester, job=ready_job, target_identity=IDENTITY)
    dispatch = Mock()
    monkeypatch.setattr(tasks.run_import_job_task, "delay", dispatch)
    with import_run_lock(ready_job.pk) as live_run:
        assert live_run.acquired
        assert cleanup.resume_stalled_materializations(
            now=timezone.now() + timedelta(minutes=3),
        ) == 0
    dispatch.assert_not_called()


def test_sweep_skips_materialized_target_and_missing_request(
    requester, ready_job, pending_job, settings, monkeypatch,
):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    claim_import_job(actor=requester, job=ready_job, target_identity=IDENTITY)
    target = Makerspace.objects.create(name="Already Imported", slug="already-imported")
    TenantImportJob.objects.filter(pk=ready_job.pk).update(target_makerspace=target)
    pending_job(status=TenantImportJob.Status.MATERIALIZING, run_request={})
    dispatch = Mock()
    monkeypatch.setattr(tasks.run_import_job_task, "delay", dispatch)
    assert cleanup.resume_stalled_materializations(now=timezone.now() + timedelta(minutes=3)) == 0
    dispatch.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("authority_loss", ["demoted", "deleted", "missing"])
def test_requester_authority_loss_is_terminal_and_not_retried(
    requester, ready_job, settings, monkeypatch, authority_loss,
):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    requester_id = requester.pk
    if authority_loss == "demoted":
        claim_import_job(actor=requester, job=ready_job, target_identity=IDENTITY)
        User.objects.filter(pk=requester_id).update(is_active=False)
    else:
        # AuditLog.actor is PROTECT: a normally claimed request would prevent
        # deleting its requester. Construct the dangling JSON provenance directly
        # to cover a historical/deleted requester without rewriting audit history.
        if authority_loss == "deleted":
            requester.delete()
        TenantImportJob.objects.filter(pk=ready_job.pk).update(
            status="materializing", run_request={
                "actor_id": requester_id if authority_loss == "deleted" else None,
                "target_identity": IDENTITY,
            },
        )
    decrypt = Mock(side_effect=AssertionError("refused requester must not read archives"))
    monkeypatch.setattr("apps.tenant_migration.import_staging.decrypted_archive", decrypt)
    monkeypatch.setattr(tasks.run_import_job_task, "delay", tasks.run_import_job_task.run)
    now = timezone.now() + timedelta(minutes=3)
    assert cleanup.resume_stalled_materializations(now=now) == 1
    ready_job.refresh_from_db()
    assert ready_job.status == "failed"
    assert ready_job.failure_code == "forbidden"
    assert ready_job.terminal_at is not None
    event = AuditLog.objects.get(action="tenant_migration.import_run_refused")
    assert event.meta == {
        "import_id": str(ready_job.pk), "failure_code": "forbidden", "format_version": 1,
    }
    assert event.actor_id == (requester_id if authority_loss == "demoted" else None)
    assert cleanup.resume_stalled_materializations(now=now + timedelta(minutes=6)) == 0
    assert AuditLog.objects.filter(action="tenant_migration.import_run_refused").count() == 1
    decrypt.assert_not_called()


def test_broker_view_dispatches_requester_and_identity(requester, ready_job, settings, monkeypatch):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    dispatch = Mock()
    monkeypatch.setattr(tasks.run_import_job_task, "delay", dispatch)
    response = request_run(requester, ready_job)
    assert response.status_code == 202
    dispatch.assert_called_once_with(str(ready_job.pk), requester.pk, IDENTITY)
    ready_job.refresh_from_db()
    assert ready_job.run_request == {"actor_id": requester.pk, "target_identity": IDENTITY}


def test_broker_enqueue_failure_retains_503_contract(requester, ready_job, settings, monkeypatch):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    dispatch = Mock(side_effect=RuntimeError("broker down"))
    monkeypatch.setattr(tasks.run_import_job_task, "delay", dispatch)
    response = request_run(requester, ready_job)
    assert response.status_code == 503
    assert response.data["code"] == "worker_unavailable"
    ready_job.refresh_from_db()
    assert ready_job.status == "failed"
    assert ready_job.failure_code == "worker_unavailable"
    assert ready_job.terminal_at is not None
    dispatch.assert_called_once_with(str(ready_job.pk), requester.pk, IDENTITY)


def test_terminal_scrub_clears_request_and_attempt(ready_job, requester):
    TenantImportJob.objects.filter(pk=ready_job.pk).update(
        status=TenantImportJob.Status.FAILED, run_attempt=uuid4(),
        run_request={"actor_id": requester.pk, "target_identity": IDENTITY},
    )
    scrubbed = scrub_terminal_job(ready_job)
    assert scrubbed.run_request == {}
    assert scrubbed.run_attempt is None
    ready_job.refresh_from_db()
    assert ready_job.run_request == {}
    assert ready_job.run_attempt is None


def test_recovery_task_returns_sum_of_three_sweeps(monkeypatch):
    finalizing, pending, materializing = Mock(return_value=2), Mock(return_value=3), Mock(return_value=7)
    for name, sweep in (
        ("resume_expired_finalizing_import_jobs", finalizing),
        ("resume_stale_pending_import_jobs", pending),
        ("resume_stalled_materializations", materializing),
    ):
        monkeypatch.setattr(tasks, name, sweep)
    assert tasks.resume_expired_finalizing_import_jobs_task.run() == 12
    for sweep in (finalizing, pending, materializing):
        sweep.assert_called_once_with()
