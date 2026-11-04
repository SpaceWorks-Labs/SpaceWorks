"""Discover existing persisted domain rows; domain tasks retain their own claims."""
from django.apps import apps
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from . import bounded


def candidates(key):
    if key == "bulk-import":
        return apps.get_model("admin_api", "BulkImportJob").objects.filter(status="pending")
    if key == "staff-export":
        return apps.get_model("data_export", "DataExportJob").objects.filter(
            status="pending", migration_export__isnull=True, expires_at__gt=timezone.now(),
        ).exclude(fidelity="SUBJECT")
    if key == "audit-verification":
        events = apps.get_model("audit", "AuditVerificationRunEvent").objects.filter(
            run_id=OuterRef("pk")).order_by("-pk").values("state")[:1]
        return apps.get_model("audit", "AuditVerificationRun").objects.annotate(
            latest_state=Subquery(events)).filter(latest_state__in=("QUEUED", "RETRYING"))
    if key == "tenant-export":
        return apps.get_model("tenant_migration", "TenantMigrationExportJob").objects.filter(
            export_job__status="pending", export_job__expires_at__gt=timezone.now())
    rows = apps.get_model("tenant_migration", "TenantImportJob").objects.filter(
        expires_at__gt=timezone.now(), actor_id__isnull=False)
    if key == "tenant-import-stage":
        return rows.filter(status="pending")
    return rows.filter(status="materializing", target_makerspace__isnull=True).exclude(run_request={})


def execute(key, *, limit, fence, context=None):
    if context is not None and key == "bulk-import":
        from apps.admin_api.cloud_work import chunk
        return bounded.invoke(context, lambda: chunk(context))
    from .work import WORK
    work = next(item for item in WORK if item.key == key)
    module, _, name = work.task.rpartition(".")
    from importlib import import_module
    callback = getattr(import_module(module), name)

    def run():
        rows = candidates(key).order_by("pk")[:limit]
        for row in bounded.page(rows, "work:" + key):
            fence()
            args = [str(row.pk)]
            if key == "tenant-import-stage":
                args.append(row.actor_id)
            elif key == "tenant-import":
                args.extend((row.run_request.get("actor_id"), row.run_request.get("target_identity")))
            result = callback(*args)
            fence()
            _require_domain_success(key, row, result)
    if context is not None:
        return bounded.invoke(context, run)
    run()
    return {"failed": 0}


def _require_domain_success(key, row, result):
    from .outcomes import TaskReportedFailure
    if key == "audit-verification":
        state = apps.get_model("audit", "AuditVerificationRunEvent").objects.filter(
            run_id=row.pk).order_by("-pk").values_list("state", flat=True).first()
        if state in {"FAILED", "TIMED_OUT", "INCOMPLETE"}:
            raise TaskReportedFailure()
        return
    if key == "tenant-export":
        state = apps.get_model("data_export", "DataExportJob").objects.values_list("status", flat=True).get(pk=row.pk)
    else:
        state = type(row).objects.values_list("status", flat=True).get(pk=row.pk)
    if state in {"failed", "abandoned"}:
        raise TaskReportedFailure()


def bulk_import(**kwargs):
    return execute("bulk-import", **kwargs)


def staff_export(**kwargs):
    return execute("staff-export", **kwargs)


def audit_verification(**kwargs):
    return execute("audit-verification", **kwargs)


def tenant_export(**kwargs):
    return execute("tenant-export", **kwargs)


def tenant_import_stage(**kwargs):
    return execute("tenant-import-stage", **kwargs)


def tenant_import(**kwargs):
    return execute("tenant-import", **kwargs)
