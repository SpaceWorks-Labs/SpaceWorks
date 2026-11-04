"""Materialize the full source database from one exported snapshot."""

import logging
import os
from pathlib import Path
import subprocess

from django.conf import settings

from apps.backup.postgres_client import client_binary

from .tenant_dump_errors import TenantDumpBuildError


logger = logging.getLogger(__name__)


def capture_database_image(snapshot_id, destination):
    from apps.backup.cloud_database_tools import configuration_spec
    from apps.backup.postgres_client import run_client
    from apps.backup.cloud_continuity import guarded_effect
    destination = Path(destination)
    try:
        selectors = []
        if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed":
            from .cloud_portable import registered_tables
            selectors = ["--data-only"]
            selectors += [f'--table=public."{table}"' for table in sorted(registered_tables())]
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_depend d ON d.objid=c.oid JOIN pg_class t ON t.oid=d.refobjid WHERE c.relkind='S' AND t.relname=ANY(%s) AND n.nspname='public'", [sorted(registered_tables())])
                selectors += [f'--table="{schema}"."{name}"' for schema, name in cursor.fetchall()]
        guarded_effect(run_client, "pg_dump", ["--format=custom", "--no-owner", "--no-acl", *selectors,
            f"--snapshot={snapshot_id}", f"--file={destination}"],
            spec=configuration_spec(settings.DATABASES["default"]))
        destination.chmod(0o600)
    except Exception:
        raise TenantDumpBuildError("The Lane D database image could not be captured.") from None
    return destination
