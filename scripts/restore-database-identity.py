#!/usr/bin/env python3
"""Report the queried bundled database identity without exposing connection secrets."""
import os
import sys
from urllib.parse import urlsplit

import psycopg


try:
    url = os.environ["DATABASE_URL"]
    endpoint = urlsplit(url)
    if endpoint.hostname != "db" or (endpoint.port or 5432) != 5432:
        raise ValueError("Legacy restore requires the bundled database endpoint.")
    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_database(), d.oid, i.database_uuid "
            "FROM pg_database d CROSS JOIN backup_deploymentdatabaseidentity i "
            "WHERE d.datname=current_database() AND i.id=1"
        )
        rows = cursor.fetchall()
        if len(rows) != 1:
            raise ValueError("Missing database identity singleton.")
        print("|".join(map(str, rows[0])))
except Exception:
    sys.exit("Cannot prove the active bundled database identity; legacy restore refused.")
