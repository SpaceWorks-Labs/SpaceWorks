"""Finite management writers participate in the same drain as HTTP and task work."""
import os

WRITERS = frozenset({
    "setup_instance", "setup_platform_email", "verify_storage",
    "reconcile_cloud_email", "reconcile_cloud_storage", "bind_legacy_storage_receipts",
    "export_tenant_migration_archive", "export_portable_tenant_dump",
})


def execute(argv, callback):
    if os.environ.get("SPACEWORKS_DEPLOYMENT_MODE", "host") != "managed" or len(argv) < 2 or argv[1] not in WRITERS:
        return callback(argv)
    import django
    django.setup()
    from apps.operations.cloud_runtime import writer
    with writer("job"):
        return callback(argv)
