"""Backfill a space's storage counter the first time a storage limit is set on it (owner rule 261).

``add_storage``/``free_storage`` now count every space, but a space that never had hosting accounting
(an own or self-host space, or one created before) carries a stale ``storage_bytes_used``. When the
superadmin sets the FIRST storage limit (``storage``, ``storage_evidence_bytes`` or
``storage_public_images_bytes``) the counter is recomputed from the canonical rows with the existing
``recompute_storage`` command, inside the caller's transaction and under the Makerspace row lock, so
the first check after the save already sees the true figure and no upload can slip between the two.
"""
import logging
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

logger = logging.getLogger(__name__)

STORAGE_LIMIT_KEYS = ("storage", "storage_evidence_bytes", "storage_public_images_bytes")


def _storage_limited(overrides) -> bool:
    for key in STORAGE_LIMIT_KEYS:
        value = (overrides or {}).get(key)
        if value is not None and not isinstance(value, bool) and value != -1:
            return True
    return False


def backfill_storage(makerspace) -> bool:
    """Recompute ``storage_bytes_used`` now; False when the command refused or could not read storage."""
    try:
        call_command("recompute_storage", str(makerspace.pk), stdout=StringIO())
    except CommandError:
        logger.warning("storage backfill skipped: space not servable", extra={"makerspace_id": makerspace.pk})
        return False
    makerspace.refresh_from_db(fields=["storage_bytes_used"])
    return True


def backfill_if_newly_limited(makerspace, old, new) -> bool:
    """Call before saving ``new`` overrides: backfill when no storage limit was set before and one is now."""
    if _storage_limited(old) or not _storage_limited(new):
        return False
    return backfill_storage(makerspace)
