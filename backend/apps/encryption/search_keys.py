"""Per-space blind-index keys (#120): derived per makerspace, rotated per makerspace.

key = HMAC-SHA256(PII_SEARCH_HASH_KEY, label || makerspace_id || version || salt)

A space with no ``MakerspaceSearchKey`` row keeps the deployment key exactly as before
(rows carry ``space_key_version = NULL``), so nothing changes until a superadmin rotates a
space's search key from ``/control/``. While a new key is BUILDING, writes already use it
and search consults both keys, so the background re-index never hides a row. Account
email lookups (``AccountPiiKey``) are deployment-wide and stay on their own global key.
"""

import hashlib
import hmac
import secrets

from django.db import transaction
from django.utils import timezone

from .models_rotation import MakerspaceSearchKey

_LABEL = b"spaceworks:space-search-key:v1\0"


def derive(makerspace_id, version, salt):
    from .blind_index import search_key
    message = _LABEL + f"{int(makerspace_id)}:{int(version)}\0".encode("ascii") + bytes(salt)
    return hmac.new(search_key(), message, hashlib.sha256).digest()


def _rows(makerspace_id):
    return list(MakerspaceSearchKey.objects.filter(
        makerspace_id=makerspace_id, status__in=("building", "active")).order_by("version"))


def write_key(makerspace_id):
    """(space_key_version or None, key bytes) that new index rows are written with."""
    rows = _rows(makerspace_id)
    chosen = next((row for row in rows if row.status == "building"), None) or (rows[-1] if rows else None)
    if chosen is None:
        from .blind_index import search_key
        return None, search_key()
    return chosen.version, derive(makerspace_id, chosen.version, chosen.salt)


def search_keys(makerspace_id):
    """Every (version or None, key) a candidate search must consult for this space."""
    rows = _rows(makerspace_id)
    if not rows:
        from .blind_index import search_key
        return [(None, search_key())]
    keys = [(row.version, derive(makerspace_id, row.version, row.salt)) for row in rows]
    if not any(row.status == "active" for row in rows):
        from .blind_index import search_key
        keys.insert(0, (None, search_key()))  # the first rotation: rows still on the global key
    return keys


def start_building(makerspace_id):
    """Create the next BUILDING key; the caller holds the makerspace's job lock."""
    with transaction.atomic():
        latest = MakerspaceSearchKey.objects.select_for_update().filter(
            makerspace_id=makerspace_id).order_by("-version").first()
        return MakerspaceSearchKey.objects.create(
            makerspace_id=makerspace_id, version=(latest.version + 1) if latest else 1,
            salt=secrets.token_bytes(32), status=MakerspaceSearchKey.Status.BUILDING)


def activate(makerspace_id, version):
    now = timezone.now()
    with transaction.atomic():
        MakerspaceSearchKey.objects.filter(makerspace_id=makerspace_id, status="active").update(
            status="retired", retired_at=now)
        MakerspaceSearchKey.objects.filter(makerspace_id=makerspace_id, version=version, status="building").update(
            status="active", activated_at=now)
