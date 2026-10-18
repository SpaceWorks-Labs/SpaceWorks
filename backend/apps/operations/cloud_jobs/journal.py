"""Short coordination transactions; model declarations/migrations belong to I.

An interrupted 'running' state is uncertain even when its guard is now available.
No elapsed lease can prove that a provider stopped accepting an old request.
"""
from datetime import timedelta
from uuid import uuid4

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from .contracts import GuardLost


def model(name):
    return apps.get_model("operations", name)


def prepare(tasks):
    now = timezone.now()
    for task in tasks:
        model("CloudTaskState").objects.get_or_create(key=task.key, defaults={
            "next_due_at": now if task.critical else now + timedelta(minutes=task.minutes),
        })
    return {row.key: row for row in model("CloudTaskState").objects.filter(key__in=[t.key for t in tasks])}


@transaction.atomic
def claim(task, guard, *, due_required=True):
    guard.check()
    row = model("CloudTaskState").objects.select_for_update().get(key=task.key)
    now = timezone.now()
    if row.status in {"running", "uncertain"}:
        row.status, row.failure_code = "uncertain", "operator_reconciliation_required"
        row.save(update_fields=["status", "failure_code"])
        record(None, "cloud.task_uncertain", meta={"task_key": task.key, "generation": row.generation})
        return None, "operator_reconciliation_required"
    if due_required and row.next_due_at and row.next_due_at > now:
        return None, "not_due"
    row.token, row.generation = uuid4(), row.generation + 1
    row.status, row.last_attempt_at, row.heartbeat_at, row.failure_code = "running", now, now, ""
    row.save(update_fields=["token", "generation", "status", "last_attempt_at", "heartbeat_at", "failure_code"])
    record(None, "cloud.task_started", meta={"task_key": task.key, "generation": row.generation})
    return row, ""


def check_token(row, guard):
    guard.check()
    if not model("CloudTaskState").objects.filter(
        pk=row.pk, token=row.token, generation=row.generation, status="running",
    ).update(heartbeat_at=timezone.now()):
        raise GuardLost()
    guard.check()


@transaction.atomic
def finish(row, task, *, status, checkpoint=None, code="", guard=None):
    if guard is not None:
        guard.check()
    locked = model("CloudTaskState").objects.select_for_update().get(pk=row.pk)
    if locked.token != row.token or locked.generation != row.generation or locked.status != "running":
        raise GuardLost()
    locked.status, locked.failure_code = status, code
    if checkpoint is not None:
        locked.checkpoint = checkpoint
    now = timezone.now()
    if status == "completed":
        locked.last_completed_at = now
        locked.next_due_at = now + timedelta(minutes=task.minutes)
    # Deferred/failed work remains due; incomplete pages are never sweep success.
    locked.save(update_fields=["status", "failure_code", "checkpoint", "last_completed_at", "next_due_at"])
    if status == "completed":
        from django.conf import settings
        from apps.operations.models_scheduling import PeriodicTaskRun
        values = {"last_error": ""}
        if getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free":
            values["last_run_at"] = now
        PeriodicTaskRun.objects.update_or_create(name=task.key, defaults=values,
            create_defaults={"last_run_at": now, "last_error": ""})
    record(None, "cloud.task_finished", meta={
        "task_key": task.key, "generation": row.generation, "status": status, "code": code,
    })


def start_tick():
    with transaction.atomic():
        row = model("CloudTickRun").objects.create()
        record(None, "cloud.tick_started", meta={"tick_id": str(row.pk)})
        return row


def finish_tick(row, payload, failed):
    with transaction.atomic():
        row.finished_at, row.duration_ms = timezone.now(), int(payload["elapsed_seconds"] * 1000)
        row.status = "failed" if failed else "completed"
        row.completed, row.deferred, row.failed = (payload[k] for k in ("completed", "deferred", "failed"))
        row.save(update_fields=["finished_at", "duration_ms", "status", "completed", "deferred", "failed"])
        record(None, "cloud.tick_finished", meta={
            "tick_id": str(row.pk), "duration_ms": row.duration_ms, "completed": row.completed,
            "deferred": row.deferred, "failed": row.failed,
        })


def prune_tick_history(*, days=30, limit=100):
    """Only bounded, finished operational detail expires; audit never does."""
    if type(days) is not int or not 1 <= days <= 365 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid tick retention policy")
    with transaction.atomic():
        ids = list(model("CloudTickRun").objects.filter(
            finished_at__lt=timezone.now() - timedelta(days=days),
        ).order_by("finished_at", "pk").values_list("pk", flat=True)[:limit])
        if ids:
            model("CloudTickRun").objects.filter(pk__in=ids).delete()
            record(None, "cloud.tick_history_pruned", meta={"count": len(ids), "retention_days": days})
