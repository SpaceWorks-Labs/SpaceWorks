"""Celery entry points for per-space restore, plus the bounded resume sweep.

Requests dispatch the preview and apply steps straight away. The sweep picks up any
step whose dispatch was lost (and runs them brokerless on the free profile), one
operation per tick, and fails a step that was interrupted mid-way so the operator sees
it instead of a restore that never moves.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)
STALE_PREVIEW = timedelta(minutes=30)
STALE_APPLY = timedelta(hours=2)


@shared_task(bind=True, max_retries=0)
def run_space_restore_preview_task(self, op_id):
    from .space_restore_runner import run_preview
    op = run_preview(op_id)
    return bool(op and op.stage == "preview_ready")


@shared_task(bind=True, max_retries=0)
def run_space_restore_apply_task(self, op_id):
    from .space_restore_runner import run_apply
    op = run_apply(op_id)
    return bool(op and op.stage == "completed")


@shared_task(bind=True, max_retries=0)
def resume_space_restores_task(self):
    from .models import MakerspaceRestoreOperation as Op
    from .space_restore_plan import SpaceRestoreError
    from .space_restore_runner import run_apply, run_preview
    from .space_restore_services import fail

    now = timezone.now()
    for op in Op.objects.filter(stage=Op.Stage.STAGING, updated_at__lt=now - STALE_PREVIEW)[:10]:
        fail(op.pk, (Op.Stage.STAGING,), SpaceRestoreError("preview_interrupted", "The preview was interrupted."))
    for op in Op.objects.filter(stage=Op.Stage.APPLYING, applied_at__lt=now - STALE_APPLY)[:10]:
        fail(op.pk, (Op.Stage.APPLYING,), SpaceRestoreError(
            "apply_interrupted", "The restore was interrupted; check the space and its safety backup."))
    queued = Op.objects.filter(stage=Op.Stage.REQUESTED, created_at__lt=now - timedelta(minutes=2)).first()
    if queued is not None:
        return bool(run_preview(queued.pk))
    waiting = Op.objects.filter(stage=Op.Stage.APPLYING, applied_at__isnull=True,
                                updated_at__lt=now - timedelta(minutes=2)).first()
    if waiting is not None:
        return bool(run_apply(waiting.pk))
    return False


def _dispatch(task, op):
    try:
        task.delay(str(op.pk))
    except Exception:
        # The resume sweep runs it on its next tick.
        logger.warning("space_restore_dispatch_failed", extra={"restore_id": str(op.pk)})


def dispatch_preview(op):
    _dispatch(run_space_restore_preview_task, op)


def dispatch_apply(op):
    _dispatch(run_space_restore_apply_task, op)
