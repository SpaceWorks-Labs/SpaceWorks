"""Supervised abandoned-pause recovery proves physical session and transfer drain."""
from contextlib import ExitStack

from django.db import transaction
from django.utils import timezone

from apps.audit.services import record
from config.cloud_database.locks import session_locks
from .models import ManagedCaptureState, ManagedWriterBoundary
from .writers import _state, writer_key, finish_capture, WriterFenceError


def recover_pause(owner, guard, actor):
    from apps.tenant_migration.services_import_job import _require_superadmin
    from .capture import _capture
    _require_superadmin(actor)
    guard.assert_valid()
    state = ManagedCaptureState.objects.get(pk=1)
    if state.paused_by != owner or state.drain_until is None or timezone.now() < state.drain_until:
        raise WriterFenceError("The abandoned owner and complete presign/transfer drain must be proven.")
    # The retained global operation lock proves the original capture owner is
    # absent. Every managed writer held its own physical session lock BEFORE its
    # boundary row committed. Try-lock failure is never interpreted as drain.
    with ExitStack() as stack:
        rows = list(ManagedWriterBoundary.objects.filter(finished_at=None).order_by("pk"))
        for row in rows:
            stack.enter_context(session_locks([writer_key(row.pk)], timeout=0))
        with transaction.atomic():
            current = _state()
            guard.assert_valid()
            if current.paused_by != owner or current.drain_until > timezone.now():
                raise WriterFenceError("The capture owner changed during reconciliation.")
            for row in rows:
                if row.started_at >= current.paused_at:
                    raise WriterFenceError("An unclassified post-pause writer requires investigation.")
            ManagedWriterBoundary.objects.filter(pk__in=[row.pk for row in rows], finished_at=None).update(
                finished_at=timezone.now(), uncertain=False)
            token = _capture.set((owner, guard, None))
            try:
                record(actor, "deployment.capture_reconciled", meta={"generation": current.generation,
                    "writer_count": len(rows)})
                finish_capture(owner, guard)
            finally:
                _capture.reset(token)
