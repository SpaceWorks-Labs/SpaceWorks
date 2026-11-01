"""The reconstruction a restore drill runs in its isolated scratch database.

The scratch database gets this deployment's SCHEMA (``pg_dump --schema-only``: catalog
only, never a row of live data) in two steps: tables, defaults, NOT NULL and CHECK
rules first; then, after every archived row is inserted, primary keys, unique
constraints and indexes. Foreign keys and triggers are left out on purpose: a one-space
archive references accounts and global rows it does not carry, and the drill proves the
archive's own rows, not the live graph (which the real restore's preview checks).

Checks: every archived row fits the schema (B2's ``prepared_record``), inserts, and the
scratch tables then hold exactly the archived row counts with unique keys intact; every
archived object's bytes match their recorded SHA-256.
"""
import hashlib
from collections import Counter
from pathlib import Path

from django.apps import apps
from django.db import DatabaseError, connections

from .projection_databases import _client, _run as _raw_run, temporary_database
from .slice_rows import SLICE_ROW_SPECS
from .space_restore_plan import SpaceRestoreError, prepared_record

SKIPPED_ENTRIES = (" FK CONSTRAINT ", " TRIGGER ", " POLICY ", " ROW SECURITY ")


def reconstruct(archive, workdir):
    schema = Path(workdir, "schema.dump")
    live_name = connections["default"].settings_dict["NAME"]
    _run([_client("pg_dump"), "--schema-only", "--format=custom", "--no-owner", "--no-acl",
          f"--dbname={live_name}", f"--file={schema}"])
    with temporary_database("drill") as (alias, name):
        if name == live_name or alias == "default":
            raise SpaceRestoreError("drill_not_isolated", "The drill database must not be the live database.")
        _run([_client("pg_restore"), "--section=pre-data", "--no-owner", "--no-acl", f"--dbname={name}", str(schema)])
        rows = _insert_all(archive, connections[alias])
        _post_data(schema, workdir, name)
        counts = _counts(connections[alias], rows)
        connections[alias].close()
    objects = _verify_objects(archive)
    return {"rows": counts, "row_total": sum(counts.values()), "labels": len(counts),
            "objects_verified": objects, "database_isolated": True}


def _run(command):
    """The scratch database tools, with the client's own complaint kept for the drill report."""
    try:
        return _raw_run(command)
    except Exception as exc:
        cause = exc.__context__
        while cause is not None and not getattr(cause, "stderr", None):
            cause = cause.__context__
        tail = (getattr(cause, "stderr", b"") or b"")[-240:].decode("utf-8", "replace").strip()
        raise SpaceRestoreError("drill_database_failed",
                                f"{command[0].rsplit('/', 1)[-1]} failed: {tail or 'no detail'}") from None


def _insert_all(archive, connection):
    expected = Counter()
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        for label in sorted(SLICE_ROW_SPECS):
            model = apps.get_model(label)
            for record in archive.rows(label):
                columns, values = prepared_record(model, record, connection)
                try:
                    cursor.execute(
                        f"INSERT INTO {quote(model._meta.db_table)} ({', '.join(quote(c) for c in columns)}) "
                        f"VALUES ({', '.join(['%s'] * len(values))})", values)
                except DatabaseError as exc:
                    raise SpaceRestoreError("drill_row_rejected", f"{label} row {record['pk']} does not restore: "
                                            f"{str(exc).splitlines()[0][:200]}") from None
                expected[model._meta.db_table] += 1
    return expected


def _post_data(schema, workdir, name):
    listing = _run([_client("pg_restore"), "-l", str(schema)]).stdout.decode("utf-8", "replace")
    selected = Path(workdir, "post-data.list")
    selected.write_text("\n".join(line for line in listing.splitlines()
                                  if not any(entry in line for entry in SKIPPED_ENTRIES)), encoding="utf-8")
    try:
        _run([_client("pg_restore"), "--section=post-data", "--no-owner", "--no-acl", f"--use-list={selected}",
              f"--dbname={name}", str(schema)])
    except SpaceRestoreError as exc:
        raise SpaceRestoreError("drill_keys_invalid", f"The restored rows break a key or index rule: {exc}") from None


def _counts(connection, expected):
    quote = connection.ops.quote_name
    found = {}
    with connection.cursor() as cursor:
        for table, count in sorted(expected.items()):
            cursor.execute(f"SELECT count(*) FROM {quote(table)}")
            found[table] = cursor.fetchone()[0]
            if found[table] != count:
                raise SpaceRestoreError("drill_row_count", f"{table} holds {found[table]} rows, expected {count}.")
    return found


def _verify_objects(archive):
    verified = 0
    for item in archive.manifest.get("storage", {}).get("objects", []):
        if item.get("retention_state") == "expired":
            continue
        path = archive.object_path(item)
        if not path.is_file() or _digest(path) != item.get("sha256"):
            raise SpaceRestoreError("drill_object_mismatch", f"Archived object {item.get('key')!r} does not verify.")
        verified += 1
    return verified


def _digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
