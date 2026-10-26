"""Producer-only reconstruction of a frozen shell in an unserved scratch database."""

from contextlib import contextmanager
import re

from django.db import connections

from .build_errors import BackupBuildError
from .slice_merge_raw import prepared_record
from .staff_shells import shell_fixture


def reconstruct_shell(cursor, model, item):
    """The live restore uses the merge role; this proof runs only in a clone."""
    if model._meta.label != "accounts.User" or "_shell_postimage" not in item:
        return False
    expected = shell_fixture(item)
    if expected["fields"] != item["_shell_postimage"]["fields"]:
        raise BackupBuildError("Reconstruction received an undeclared staff shell.")
    columns, values = prepared_record(model, expected, cursor.db)
    cursor.execute("SELECT * FROM accounts_user WHERE id = %s FOR UPDATE", [item["pk"]])
    row = cursor.fetchone()
    if row is None or dict(zip((c[0] for c in cursor.description), row, strict=True)) != dict(zip(columns, values, strict=True)):
        raise BackupBuildError("Reconstruction staff identity is not its exact projected shell.")
    columns, values = prepared_record(model, item, cursor.db)
    quote = cursor.db.ops.quote_name
    cursor.execute("UPDATE accounts_user SET " + ", ".join(f"{quote(c)} = %s" for c in columns)
                   + " WHERE id = %s", [*values, item["pk"]])
    return True


@contextmanager
def reconstruction_context(using):
    # Only the disposable producer clone uses this schema operation. Live restore
    # never enters this context; its one-way guard calls the registered merge proof.
    if not re.fullmatch(r"backup_reconstruction_[0-9a-f]{32}", using):
        raise BackupBuildError("Staff reconstruction requires its disposable database alias.")
    connection = connections[using]
    name = connection.settings_dict["NAME"]
    if not name.startswith("spaceworks_backup_reconstruction_") or name == connections["default"].settings_dict["NAME"]:
        raise BackupBuildError("Staff reconstruction cannot run against a served database.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != name:
            raise BackupBuildError("The reconstruction connection names a different database.")
        cursor.execute("ALTER TABLE accounts_user DISABLE TRIGGER accounts_user_context_immutable")
    try:
        yield
    finally:
        with connections[using].cursor() as cursor:
            cursor.execute("ALTER TABLE accounts_user ENABLE TRIGGER accounts_user_context_immutable")
