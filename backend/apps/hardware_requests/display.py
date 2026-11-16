"""Readable requester display labels for STAFF-facing surfaces.

Legacy self-checkout shadow users carry the privacy hash username ``checkin_<sha256>``
from the retired Check-In integration. Showing that raw hash in reports/queues is useless
to staff. This module resolves a human-readable label — the request's captured name or
contact fields, then the account — skipping the internal hash, with a generic
``"Member"`` fallback.

This is a PII display: the returned label can be a contact email/phone. It is only
appropriate on staff/superadmin surfaces that are RBAC-action-gated and tenant-scoped
(the same data the operations ledger already shows staff). Public surfaces must NOT
use this — they use ``inventory.public_stats.public_display_name`` ("Member").
"""


def clean_label(value):
    return str(value or "").strip()


def looks_like_email(value):
    return "@" in value


def is_internal_checkin_username(value):
    # Mirrors the operations-ledger guard: a ``checkin_<sha256>`` shadow username
    # (the local-part before any ``@``) is the internal privacy hash, never a name.
    local_part = value.split("@", 1)[0]
    return local_part.startswith("checkin_") and len(local_part) > 32


def requester_label(request, *, fallback="Member", allow_internal_fallback=False):
    """Readable label for a HardwareRequest/PrintRequest-like row.

    Prefers the captured requester name, then a real email (contact email → account
    email → username), then any non-hash identifier (contact phone → username →
    account username). ``allow_internal_fallback`` is accepted for the ledger's call
    but changes nothing: the internal check-in hash is never shown (its former second
    pass repeated the first one exactly and could not return anything new).
    """
    requester = getattr(request, "requester", None)

    name = clean_label(getattr(request, "requester_name", ""))
    if name:
        return name

    email_candidates = [
        getattr(request, "requester_contact_email", ""),
        getattr(requester, "email", ""),
        getattr(request, "requester_username", ""),
    ]
    for value in email_candidates:
        label = clean_label(value)
        if looks_like_email(label) and not is_internal_checkin_username(label):
            return label

    candidates = [
        getattr(request, "requester_contact_phone", ""),
        getattr(request, "requester_username", ""),
        getattr(requester, "username", ""),
    ]
    for value in candidates:
        label = clean_label(value)
        if label and not is_internal_checkin_username(label):
            return label

    return fallback


def label_from_candidates(*values, fallback="Member"):
    """First non-empty, non-hash candidate (in priority order), else ``fallback``.

    For surfaces whose field names don't match :func:`requester_label` (e.g. a
    PrintRequest, which carries ``requester_name``/``contact_email``/``contact_phone``).
    """
    for value in values:
        label = clean_label(value)
        if label and not is_internal_checkin_username(label):
            return label
    return fallback


def _safe_username(value):
    label = clean_label(value)
    phone_like = label.lstrip("+").replace(" ", "").replace("-", "").isdigit()
    if label and not looks_like_email(label) and not is_internal_checkin_username(label) and not phone_like:
        return label
    return ""


def account_name_label(user, *, fallback="Member"):
    """An account's display or full name, else a username that is not contact data, else ``fallback``."""
    if user is None:
        return fallback
    for value in (getattr(user, "display_name", ""), user.get_full_name() if hasattr(user, "get_full_name") else ""):
        if clean_label(value):
            return clean_label(value)
    return _safe_username(getattr(user, "username", "")) or fallback


def requester_name_label(request, *, fallback="Member"):
    """A borrower label that NEVER falls back to contact details (email or phone).

    For surfaces whose viewer holds no loan/member-contact authority (an Event Manager reading
    their event's loans): the captured name, then the account's name or safe username, then a
    request username that is neither an email, a phone number nor the check-in hash, else ``fallback``.
    """
    name = clean_label(getattr(request, "requester_name", ""))
    if name:
        return name
    label = account_name_label(getattr(request, "requester", None), fallback="")
    return label or _safe_username(getattr(request, "requester_username", "")) or fallback
