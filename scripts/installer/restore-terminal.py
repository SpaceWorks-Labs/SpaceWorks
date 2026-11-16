#!/usr/bin/env python3
"""Prove a restore is terminal, inactive and has no rollback objects before expiry."""
import json
import logging
import os
import sys
import uuid


def main():
    logging.disable(logging.CRITICAL)
    restore_id = str(uuid.UUID(sys.argv[1]))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from apps.backup.models import DeploymentRecoveryState, RestoreOperation
    restore = RestoreOperation.objects.get(pk=restore_id)
    active = DeploymentRecoveryState.objects.filter(active_restore_id=restore_id)
    quarantine = restore.stage == "restored_quarantined" and active.filter(mode="quarantined").exists()
    if (restore.stage not in {"completed", "restored_quarantined", "failed", "aborted"}
            or restore.completed_at is None
            or (active.exists() and not quarantine)
            or restore.rollback_objects.exists()):
        raise ValueError("Restore is not safe for retention.")
    print(json.dumps({"restore_id": restore_id, "stage": restore.stage, "schema_version": 1}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Terminal restore proof failed; keep all private recovery work.")
