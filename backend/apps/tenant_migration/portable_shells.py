"""Merged shells travel PII-free (one account per person; U-A1's shell-import branch).

A shell -- an account merged into a person -- keeps history that points at it, and some of
that history is PROTECT (``AuditLog.actor``), so it cannot simply vanish from an import.
The source export writes shells without any personal data and records, in
``global/user-aliases.json``, the survivor of each shell whose survivor is also in the
archive. The import creates each shell as an inert row and re-establishes
``merged_into`` to the survivor's target account when that survivor travelled; otherwise
the shell arrives retired with no alias. Both writes happen only inside this exact running
import (``app.account_shell_import_job_id``), the one context the account guards admit.
"""

from uuid import uuid4

from django.db import connection
from django.utils import timezone

from apps.accounts.account_kind_guards import SHELL_IMPORT_GUC
from apps.accounts.models import User

from .archive_stream import database_value
from .insertion_errors import PrimaryKeyMapUnavailable

ALIASES_PATH = "global/user-aliases.json"


def create_shells(archive, job, pk_map, sources):
    """Create every travelled shell; return ``(created, remapped to a survivor)``."""
    if not sources:
        return 0, 0
    aliases = archive.json(ALIASES_PATH).get("aliases", {}) if (archive.root / ALIASES_PATH).is_file() else {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [SHELL_IMPORT_GUC, str(job.pk)])
    now, remapped = timezone.now(), 0
    for source in sources:
        survivor = _survivor(pk_map, aliases.get(str(source["id"])))
        shell = User(
            pk=pk_map.lookup(User, source["id"]), username=f"__tenant_shell__{uuid4().hex}",
            account_kind="staff", is_active=False, is_walk_in=False, is_staff=False, is_superuser=False,
            date_joined=database_value(User._meta.get_field("date_joined"), source["date_joined"]),
            access_status=User.AccessStatus.SUSPENDED, role=User.Role.REQUESTER,
            merged_into_id=survivor, merged_at=now if survivor else None,
            retired_at=None if survivor else now,
        )
        shell.set_unusable_password()
        shell.save(force_insert=True)
        remapped += survivor is not None
    return len(sources), remapped


def _survivor(pk_map, source_survivor_id):
    if not source_survivor_id:
        return None
    try:
        return pk_map.lookup(User, source_survivor_id)
    except PrimaryKeyMapUnavailable:
        return None


def write_user_aliases(root, user_rows):
    """Source side: each travelling shell's survivor, when the survivor travels too."""
    import json

    from apps.accounts.staff_identity import is_shell

    present = {row.pk for row in user_rows}
    aliases = {}
    for row in user_rows:
        if not is_shell(row) or row.merged_into_id is None:
            continue
        survivor, seen = row.merged_into_id, set()
        while survivor not in seen:
            seen.add(survivor)
            following = User._base_manager.filter(pk=survivor).values_list("merged_into_id", flat=True).first()
            if following is None:
                break
            survivor = following
        if survivor in present:
            aliases[str(row.pk)] = str(survivor)
    path = root / ALIASES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"aliases": aliases}, sort_keys=True), encoding="utf-8")
