#!/usr/bin/env python3
"""Outside-database steps of scripts/restore.sh, run inside the backend image (management role).

The host sets DATABASE_URL to the owner (maintenance) login for the one-off container, so these
steps use the same validated transport and version-matched client as the in-app backup:
apps.backup.postgres_client picks pg_dump/pg_restore by the SERVER's major (16 or 17) and
config.cloud_database refuses a transaction pooler. Nothing here accepts a connection string,
host or role on the command line.

  identity [scratch-name]       print name|oid|uuid of the connected (or scratch) database
  has-data                      print the number of accounts (0 = a freshly bootstrapped database)
  dump <file>                   pg_dump --format=custom of the connected database
  restore <file>                pg_restore --clean --if-exists into the connected database
  create-scratch <name>         create an empty sibling database for the every-table diff
  restore-scratch <name> <file> pg_restore into that sibling database
  drop-scratch <name>           drop it again
Files must sit under /var/lib/spaceworks/ops/work/.
"""
import os
import re
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.conf import settings

from apps.backup.cloud_database_tools import configuration_spec
from apps.backup.postgres_client import run_client
from config.cloud_database import connect_database

WORK = "/var/lib/spaceworks/ops/work/"
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_$]{0,62}")
IDENTITY_SQL = (
    "SELECT current_database(), d.oid, i.database_uuid "
    "FROM pg_database d CROSS JOIN backup_deploymentdatabaseidentity i "
    "WHERE d.datname=current_database() AND i.id=1"
)


def fail(message):
    sys.exit(message)


def work_file(path):
    real = os.path.realpath(path)
    if not real.startswith(WORK):
        fail("Files must sit under the private operations work directory.")
    return real


def scratch_name(name):
    if not NAME.fullmatch(name) or not name.startswith("spaceworks_restore_"):
        fail("Invalid scratch database name.")
    return name


def spec(name=None):
    return configuration_spec(settings.DATABASES["default"], name=name)


def scalar(sql, name=None):
    connection = connect_database(spec(name))
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        connection.close()


def terminate_other_sessions():
    """Best effort: a managed provider may refuse to end its own internal sessions."""
    connection = connect_database(spec())
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                           "WHERE datname=current_database() AND pid<>pg_backend_pid()")
    except Exception:
        print("Could not end every other session; continuing.", file=sys.stderr)
    finally:
        connection.close()


def main(argv):
    op, args = (argv[0] if argv else ""), argv[1:]
    if op == "identity" and len(args) <= 1:
        rows = scalar(IDENTITY_SQL, scratch_name(args[0]) if args else None)
        if len(rows) != 1:
            fail("Missing database identity singleton.")
        print("|".join(map(str, rows[0])))
    elif op == "has-data" and not args:
        present = scalar("SELECT to_regclass('public.accounts_user') IS NOT NULL")[0][0]
        print(scalar("SELECT count(*) FROM public.accounts_user")[0][0] if present else 0)
    elif op == "dump" and len(args) == 1:
        run_client("pg_dump", ["--format=custom", "--no-owner", "--no-acl", f"--file={work_file(args[0])}"], spec=spec())
    elif op == "restore" and len(args) == 1:
        terminate_other_sessions()
        run_client("pg_restore", ["--exit-on-error", "--clean", "--if-exists", "--no-owner", "--no-acl", work_file(args[0])], spec=spec())
    elif op == "create-scratch" and len(args) == 1:
        run_client("createdb", [scratch_name(args[0])], spec=spec())
    elif op == "restore-scratch" and len(args) == 2:
        run_client("pg_restore", ["--exit-on-error", "--no-owner", "--no-acl", work_file(args[1])], spec=spec(scratch_name(args[0])))
    elif op == "drop-scratch" and len(args) == 1:
        run_client("dropdb", ["--if-exists", scratch_name(args[0])], spec=spec())
    else:
        fail("Unknown outside-database restore step.")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception:
        sys.exit("Outside-database restore step failed; check privileges, TLS and that the endpoint is the direct or session connection (never a transaction pooler).")
