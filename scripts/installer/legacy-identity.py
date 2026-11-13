#!/usr/bin/env python3
"""Read-only pre-H1 admission; never display a DSN or accept an external endpoint."""
import os
import sys
from urllib.parse import unquote, urlsplit

import psycopg2


def main():
    url = os.environ["DATABASE_URL"]
    endpoint = urlsplit(url)
    if endpoint.hostname != "db" or (endpoint.port or 5432) != 5432:
        raise ValueError("Unsupported legacy database endpoint.")
    database = psycopg2.connect(url, connect_timeout=10)
    try:
        with database.cursor() as cursor:
            cursor.execute("SELECT current_database(), oid FROM pg_database WHERE datname=current_database()")
            name, oid = cursor.fetchone()
            if name != unquote(endpoint.path.lstrip("/")):
                raise ValueError("Legacy database name differs.")
            print(f"{name}|{oid}")
    finally:
        database.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Cannot prove the legacy bundled database; transition refused before writes.")
