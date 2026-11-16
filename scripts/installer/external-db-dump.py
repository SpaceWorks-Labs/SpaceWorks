#!/usr/bin/env python3
"""Pre-update dump of an outside database, run inside the backend container.

Uses the same version-matched pg_dump and validated connection transport as the in-app backup
(apps.backup.postgres_client picks the client by the server's major version and refuses a
transaction pooler). Writes /var/lib/spaceworks/ops/work/<name> and prints the database size.
"""
import os
import re
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.conf import settings
from django.db import connection

from apps.backup.cloud_database_tools import configuration_spec
from apps.backup.postgres_client import run_client

name = sys.argv[1]
if not re.fullmatch(r"pre-update-[0-9TZ]+-[0-9]+\.dump", name):
    sys.exit("Invalid dump name.")
with connection.cursor() as cursor:
    cursor.execute("SELECT pg_database_size(current_database())")
    size = cursor.fetchone()[0]
run_client("pg_dump", ["--format=custom", "--no-owner", "--no-acl", f"--file=/var/lib/spaceworks/ops/work/{name}"],
           spec=configuration_spec(settings.DATABASES["default"]))
print(size)
