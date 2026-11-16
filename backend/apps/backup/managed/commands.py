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
    from django.db import connections
    from apps.operations.cloud_runtime import writer
    # run_from_argv closes every connection when the command returns, but the writer
    # still proves its fence on the retained session as it exits; reconnecting there
    # is forbidden. Close once the writer has finished instead.
    close_all = connections.close_all
    connections.close_all = lambda: None
    try:
        with writer("job"):
            return callback(argv)
    finally:
        del connections.close_all
        close_all()
