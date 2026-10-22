#!/usr/bin/env python3
"""Report the queried bundled database identity without exposing connection secrets."""
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

import psycopg2


def main():
    """Import safely; psycopg2's connection context alone does not close it."""
    url = os.environ["DATABASE_URL"]
    endpoint = urlsplit(url)
    if endpoint.hostname != "db" or (endpoint.port or 5432) != 5432:
        raise ValueError("Legacy restore requires the bundled database endpoint.")
    connection = psycopg2.connect(url, connect_timeout=10)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(), d.oid, i.database_uuid "
                "FROM pg_database d CROSS JOIN backup_deploymentdatabaseidentity i "
                "WHERE d.datname=current_database() AND i.id=1"
            )
            rows = cursor.fetchall()
        if len(rows) != 1:
            raise ValueError("Missing database identity singleton.")
        name, oid, database_uuid = rows[0]
        if sys.argv[1:] in (["--active-name"], ["--active-proof"]):
            from apps.backup.host_marker import MarkerState, read_marker
            marker = read_marker(Path(os.environ.get(
                "SPACEWORKS_HOST_MARKER_PATH", "/run/spaceworks-host/restore-marker.json")))
            bound = marker.require_bound_database()
            if (marker.state not in {MarkerState.NORMAL, MarkerState.ACKNOWLEDGED_NORMAL}
                    or marker.database_routing != "active" or bound.name != name or bound.oid != oid
                    or bound.server_identity is None
                    or bound.server_identity["database_uuid"] != str(database_uuid)):
                raise ValueError("Active database does not match the host marker.")
            print(name if sys.argv[1:] == ["--active-name"] else "|".join(map(str, rows[0])))
        elif sys.argv[1:]:
            raise ValueError("Unknown identity operation.")
        else:
            print("|".join(map(str, rows[0])))
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Cannot prove the active bundled database identity; legacy restore refused.")
