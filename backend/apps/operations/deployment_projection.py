"""Already-authorized callers choose tenant or operator facts explicitly."""
from django.conf import settings
from django.db import connection
from django.db.models import Max


def deployment_projection(*, makerspace=None):
    mode = getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host")
    profile = getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full")
    from shutil import which
    base = {"mode": mode, "profile": profile,
            "scanner": getattr(settings, "UPLOAD_SCAN_POLICY", "none"),
            "media_validation_available": profile != "free" and which("ffprobe") is not None}
    if makerspace is not None:
        result = {**base, "scope": "tenant", "deployment_warning": mode == "managed"}
        if profile == "free":
            from .cloud_quotas.projection import free_usage
            result["objects"] = free_usage(makerspace)["objects"]
        return result
    from .models_scheduling import PeriodicTaskRun
    progress = PeriodicTaskRun.objects.filter(last_error="").aggregate(last=Max("last_run_at"))["last"]
    if mode == "managed":
        from .models import CloudTaskState
        progress = CloudTaskState.objects.aggregate(last=Max("last_completed_at"))["last"]
    result = {**base, "scope": "deployment", "topology": getattr(settings, "CLOUD_SCHEDULER", "") or "host",
        "database_transport": getattr(settings, "DATABASE_CONNECTION_MODE", "direct"),
        "database_major": connection.pg_version // 10000, "storage": [],
        "last_worker_success_at": None, "last_scheduler_success_at": progress,
        "portable_dump_available": False, "portable_dump_reason": "qualification_required",
        "provider_recovery": {"database_status": "unknown", "object_status": "unknown",
            "drill_status": "unknown", "last_drill_at": None, "reason": "offline_drill_evidence_required"}}
    if mode == "managed" or getattr(settings, "STORAGE_CAPABILITIES_FILE", ""):
        from apps.operations.models import StorageCapabilityState
        from apps.storage_capabilities.verification import verification_ttl
        from django.utils import timezone
        from datetime import timedelta
        rows = StorageCapabilityState.objects.filter(verified_at__gte=timezone.now() - timedelta(seconds=verification_ttl()))
        for row in rows:
            result["storage"].append({"label": row.logical_role or "retained storage",
                "upload": "post" if "post" in row.facts.get("presign_methods", ()) else "put",
                "versioned": row.facts.get("versioning") == "enabled", "object_lock": row.facts.get("object_lock") is True})
    if profile == "free":
        from .cloud_quotas.projection import free_usage
        result["free_usage"] = free_usage()
    return result
