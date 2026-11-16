"""What the console shows of one space's keys (#190 follow-up). No key material, salts or key values."""

from django.conf import settings

from .key_events import key_state


def state(space):
    from apps.backup.space_archive_keys import stale_space_archives
    from apps.tenant_rls.role_contract import status as rls_status
    keys = key_state(space)
    return {
        **keys,
        "running": next((job for job in keys["jobs"] if job.status == job.Status.RUNNING), None),
        "pii_encryption_enabled": bool(settings.PII_ENCRYPTION_ENABLED),
        "rls_mode": rls_status()["mode"],
        "stale_archives": [{"id": entry["archive"].pk, "completed_at": entry["archive"].completed_at,
                            "size_bytes": entry["archive"].size_bytes, "reencryptable": entry["reencryptable"],
                            "job": entry["job"]} for entry in stale_space_archives(space)],
    }
