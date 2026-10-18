"""Revalidate queued intent against the current account before archive I/O."""
from django.db import transaction
from django.utils import timezone

from apps.accounts import rbac
from apps.admin_api.permissions import active_user
from apps.audit.services import record


def allowed(actor, action, makerspace_id):
    return bool(active_user(actor) and getattr(actor, "retired_at", None) is None
                and rbac.can(actor, action, makerspace_id))


def export_allowed(job):
    actor = job.requested_by
    if not active_user(actor) or getattr(actor, "retired_at", None) is not None:
        return False
    if job.fidelity == "SUBJECT":
        return True  # The subject service rechecks active membership and feature.
    if job.fidelity == "PORTABLE":
        from apps.tenant_migration.services_import_job import _require_superadmin
        from rest_framework.exceptions import ValidationError
        try:
            _require_superadmin(actor)
        except ValidationError:
            return False
        return True
    return rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, job.makerspace_id)


def prepare_export_claim(queryset, job_id):
    job = queryset.select_related("makerspace", "requested_by").filter(pk=job_id, status="pending").first()
    if job is None:
        return False
    if not export_allowed(job):
        refuse_export(queryset, job, "integrity_error", "The requester no longer has export authority.")
        return False
    from .admission import FreeJobTooLarge, assert_export
    try:
        assert_export(job)
    except FreeJobTooLarge as exc:
        refuse_export(queryset, job, "quota_exceeded", str(exc))
        return False
    return True


def refuse_export(queryset, job, code, message):
    with transaction.atomic():
        if queryset.filter(pk=job.pk, status="pending").update(status="failed", failure_code=code,
                failure_detail=message, completed_at=timezone.now()):
            record(job.requested_by, "data_export.failed", makerspace=job.makerspace,
                   target=job, meta={"failure_code": code})
