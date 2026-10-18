from django.conf import settings
from django.db.models import Max, Q
from django.utils import timezone


def sample(*, used=None, cap=None, unit="bytes", scope="deployment", uncertain=0,
           sampled_at=None, source="unknown", reason="usage_unverified"):
    state = "unknown"
    if used is not None and sampled_at is not None:
        if (timezone.now() - sampled_at).total_seconds() > 1800:
            state = "stale"
        elif cap is not None:
            ratio = used / cap if cap > 0 else float("inf")
            state = "reached" if ratio >= 1 else "critical" if ratio >= .95 else "warning" if ratio >= .8 else "ok"
    return {"used": used, "cap": cap, "unit": unit, "state": state, "source": source,
            "cap_source": "operator_configuration" if cap is not None else "unknown", "cap_verified_on": None,
            "scope": scope, "sampled_at": sampled_at, "uncertain": uncertain, "reason_code": reason}


def tick_status():
    from apps.operations.models import CloudTaskState, CloudTickRun
    contact = CloudTickRun.objects.order_by("-started_at").first()
    progress = CloudTaskState.objects.exclude(status="disabled")
    last = progress.aggregate(value=Max("last_completed_at"))["value"]
    failed = progress.filter(Q(status__in=["failed", "uncertain"]) |
        Q(failure_code__in=["bounded_adapter_unavailable", "operator_reconciliation_required"])).count()
    interval = settings.FREE_TICK_INTERVAL_SECONDS
    age = int((timezone.now() - last).total_seconds()) if last else None
    from datetime import timedelta
    overdue = progress.filter(next_due_at__lt=timezone.now() - timedelta(seconds=interval * 2)).exists()
    # A successful contact with no completed task does not prove sweep freshness.
    return {"last_completed_at": last, "last_contact_at": contact.started_at if contact else None,
            "age_seconds": age, "interval_seconds": interval, "failed_tasks": failed,
            "state": "failed" if failed else "never" if last is None else "late" if overdue or age > interval * 2 else "ok"}


def free_usage(makerspace=None):
    from apps.integrations.models import EmailLog
    from apps.operations.models import CloudUsageSample
    tenant = makerspace is not None
    scope = "tenant" if tenant else "deployment"
    logs = EmailLog.objects.all()
    if tenant:
        logs = logs.filter(makerspace=makerspace)
    database = None
    objects = sample(scope=scope)
    if tenant:
        from apps.makerspaces.limits import resource_limit
        objects = sample(used=makerspace.storage_bytes_used, cap=resource_limit(makerspace, "storage"),
                         scope=scope, sampled_at=timezone.now(), source="tenant_accounted_bytes",
                         reason="provider_usage_outside_application_unknown")
    else:
        row = CloudUsageSample.objects.filter(metric="database", scope="deployment").order_by("-sampled_at").first()
        database = sample(used=row.used if row else None, cap=settings.FREE_DB_CAP_BYTES,
                          sampled_at=row.sampled_at if row else None, source="database_sample")
        row = CloudUsageSample.objects.filter(metric="objects", scope="deployment").order_by("-sampled_at").first()
        objects = sample(used=row.used if row else None, cap=settings.FREE_OBJECT_CAP_BYTES,
                         uncertain=row.uncertain if row else 0, sampled_at=row.sampled_at if row else None)
    email = sample(scope="tenant" if tenant else "provider_account", unit="recipients")
    if not tenant:
        try:
            from apps.integrations.models import PlatformEmailSettings
            from apps.integrations.mail_providers.selection import stored_config, environment_config
            from apps.integrations.mail_providers.budget_config import account_budget
            from apps.integrations.mail_providers.budget import usage
            row = PlatformEmailSettings.objects.filter(pk=1).first()
            if row is None:
                raise ValueError("Account policy has not been established.")
            config = stored_config(row) or environment_config()
            values = usage(account_budget(config))
            email = sample(used=sum(values[k] for k in ("accepted", "reserved", "uncertain")),
                cap=values["daily_cap"], uncertain=values["uncertain"], sampled_at=values["sampled_at"],
                source="application_account_reservations", unit="recipients", scope="provider_account",
                reason="provider_usage_outside_application_unknown")
        except Exception:
            pass  # Preserve unknown, never display missing account policy as zero.
    return {"profile": "free", "visibility": scope, "database": database, "objects": objects,
            "email": email, "email_pending": logs.filter(status="pending").count(),
            "email_uncertain": None if tenant else email["uncertain"], "tick": tick_status(),
            "notices": ["Cold starts and missed triggers can delay scheduled work.",
                        "Scheduled deployment backups and video validation are unavailable."]}
