from datetime import timedelta
from uuid import uuid4

from django.utils import timezone
from apps.audit.services import record
from apps.events.credentials.errors import ProgrammeConflict
from apps.makerspaces import limits
from .print_models import BadgePrintJob
from .print_policy import require_job
from .print_boundary import print_command


def claim(job, actor):
    with print_command(job, actor=actor) as (event, actor, scope):
        row = BadgePrintJob.objects.select_for_update().get(pk=job.pk)
        require_job(row, actor, prepared_scope=scope)
        if row.state == "ready":
            return row
        if row.state == "rendering" and row.render_started_at is not None and row.render_started_at > timezone.now()-timedelta(minutes=5):
            raise ProgrammeConflict("This print job is rendering.", code="print_in_progress")
        row.state, row.render_token, row.render_started_at = "rendering", uuid4(), timezone.now()
        row.save(update_fields=("state", "render_token", "render_started_at"))
        record(actor, "event.badge_print_claimed", makerspace=event.makerspace, target=row)
        return row


def finish(job, actor, size, digest):
    with print_command(job, actor=actor) as (event, actor, scope):
        row = BadgePrintJob.objects.select_for_update().get(pk=job.pk)
        if row.state == "ready":
            require_job(row, actor, prepared_scope=scope)
            return row
        if row.render_token != job.render_token or row.state != "rendering":
            raise ProgrammeConflict("The print render claim changed.", code="print_claim_changed")
        require_job(row, actor, prepared_scope=scope)
        if row.size_bytes != size or row.sha256 != digest:
            raise ProgrammeConflict("The rendered PDF differs from its reservation.", code="print_snapshot_changed")
        row.state, row.size_bytes, row.sha256 = "ready", size, digest
        row.save(update_fields=("state", "size_bytes", "sha256"))
        record(actor, "event.badge_print_ready", makerspace=event.makerspace, target=row,
               meta={"count": len(row.registration_ids), "size_bytes": size})
        return row


def reserve_pdf(job, actor, size, digest):
    with print_command(job, actor=actor) as (event, actor, scope):
        row = BadgePrintJob.objects.select_for_update().get(pk=job.pk)
        require_job(row, actor, prepared_scope=scope)
        if row.render_token != job.render_token or row.state != "rendering":
            raise ProgrammeConflict("The render claim changed.", code="print_claim_changed")
        if row.size_bytes and (row.size_bytes != size or row.sha256 != digest):
            raise ProgrammeConflict("The immutable print content changed.", code="print_snapshot_changed")
        if not row.size_bytes:
            limits.add_storage(event.makerspace, size)
            row.size_bytes, row.sha256 = size, digest
            row.save(update_fields=("size_bytes", "sha256"))
            record(actor, "event.badge_pdf_reserved", makerspace=event.makerspace, target=row,
                   meta={"size_bytes": size})


def fail(job):
    with print_command(job, actor=None) as (event, _, _scope):
        row = BadgePrintJob.objects.select_for_update().get(pk=job.pk)
        if row.state == "rendering" and row.render_token == job.render_token:
            row.state = "failed"
            row.save(update_fields=("state",))
            record(None, "event.badge_print_failed", makerspace=event.makerspace, target=row)
