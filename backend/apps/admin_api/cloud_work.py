"""Transactional bulk-import pages using the job's existing durable progress."""
import hashlib
import json

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.operations.cloud_jobs import bounded
from apps.operations.cloud_jobs.contracts import ChunkResult, GuardLost
from apps.tenant_migration.gate_runtime import fanout_tenant_write
from . import bulk_import
from .models import BulkImportJob
from .tasks import _job_rows


def candidates():
    return BulkImportJob.objects.filter(Q(status="pending") |
        Q(status="running", result__cloud_checkpoint__state="ready"))


def chunk(context):
    context.check()
    job = candidates().select_related("actor", "makerspace").order_by("created_at", "pk").first()
    if job is None:
        return ChunkResult(True)
    from apps.accounts import rbac
    from apps.operations.cloud_jobs.authority import allowed
    if not allowed(job.actor, rbac.Action.EDIT_INVENTORY, job.makerspace_id):
        BulkImportJob.objects.filter(pk=job.pk, status=job.status).update(
            status="failed", error="Requester authority changed.", completed_at=timezone.now())
        from apps.operations.cloud_jobs.outcomes import TaskReportedFailure
        raise TaskReportedFailure()
    rows = _job_rows(job)
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"),
                                        allow_nan=False).encode()).hexdigest()
    context.check()
    counts = {"skipped": 0}
    with fanout_tenant_write(job.makerspace_id, operation="bulk_import", counts=counts) as allowed:
        if not allowed:
            return ChunkResult(False)
        with transaction.atomic(), bounded.scope(context):
            job = candidates().select_for_update().get(pk=job.pk)
            previous = dict(job.result or {})
            checkpoint = previous.pop("cloud_checkpoint", {})
            if checkpoint.get("sha256", digest) != digest:
                raise GuardLost("bulk_import_source_changed")
            start = job.processed_rows
            page = rows[start:start + min(context.limit, 25)]
            context.check()
            result = (bulk_import.apply_import(job.actor, job.makerspace, page, job.mapping,
                                              allow_partial=True)
                      if job.mode == "apply" else bulk_import.preview_import(job.makerspace, page, job.mapping))
            context.check()
            for key in ("rows", "errors", "warnings"):
                for item in result.get(key, []):
                    item["row"] += start
                result[key] = previous.get(key, []) + result.get(key, [])
            summary = result["summary"]
            for key in summary:
                summary[key] += previous.get("summary", {}).get(key, 0)
            for key in ("created", "updated"):
                result[key] = previous.get(key, 0) + result.get(key, 0)
            job.processed_rows = start + len(page)
            complete = job.processed_rows >= len(rows)
            result["cloud_checkpoint"] = {"state": "complete" if complete else "ready", "sha256": digest}
            result["valid"] = not result["errors"]
            job.result, job.total_rows = result, len(rows)
            job.status = "completed" if complete else "running"
            job.created_count, job.updated_count = result["created"], result["updated"]
            job.error_count, job.warning_count = len(result["errors"]), len(result["warnings"])
            job.completed_at = timezone.now() if complete else None
            job.save(update_fields=["result", "total_rows", "processed_rows", "status", "created_count",
                "updated_count", "error_count", "warning_count", "completed_at", "updated_at"])
    return ChunkResult(False, processed=len(page))
