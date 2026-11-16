"""Bearer tokens for invitations and applicant status links.

The raw value exists only in the emailed link (a URL fragment) and, for an invitation,
once in the inviter's creation response. The database stores its SHA-256 digest, so a
leaked table cannot be replayed into a status page or an invitation.
"""

import hashlib
import secrets

from django.http import Http404


def digest(raw) -> str:
    value = str(raw or "").strip()
    if not 20 <= len(value) <= 200:
        raise Http404()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mint() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, digest(raw)
