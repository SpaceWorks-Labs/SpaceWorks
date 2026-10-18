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
        guarded_effect(run_client, "pg_dump", ["--format=custom", "--no-owner", "--no-acl",
            f"--snapshot={snapshot_id}", f"--file={destination}"],
            spec=configuration_spec(settings.DATABASES["default"]))
        destination.chmod(0o600)
    except Exception:
        raise TenantDumpBuildError("The Lane D database image could not be captured.") from None
    return destination
