"""Producer-clone-only inversion of projected global member-reference links.

Live slice merges retain all immutability triggers and need the exact registered
merge-role inverse. This context never runs against a served database.
"""

from contextlib import contextmanager
import re

from django.db import connections

from .recipient_selection import BackupBuildError


@contextmanager
def public_page_reconstruction_context(using):
    if not re.fullmatch(r"backup_reconstruction_[0-9a-f]{32}", using):
        raise BackupBuildError("Public page reconstruction requires its disposable database alias.")
    connection = connections[using]
    name = connection.settings_dict["NAME"]
    if not name.startswith("spaceworks_backup_reconstruction_") or name == connections["default"].settings_dict["NAME"]:
        raise BackupBuildError("Public page reconstruction cannot use a served database.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != name:
            raise BackupBuildError("Public page reconstruction connection identity differs.")
        cursor.execute("ALTER TABLE organizations_organizationpublicpagerevisionmember "
                       "DISABLE TRIGGER organizations_organizationpublicpage_immutable")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE organizations_organizationpublicpagerevisionmember "
                           "ENABLE TRIGGER organizations_organizationpublicpage_immutable")
