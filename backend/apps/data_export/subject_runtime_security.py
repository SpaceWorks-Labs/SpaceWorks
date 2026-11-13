"""A person's own login-security memory in their subject-access export (lane S-B).

Platform rows with no space, included in every space's export of that person (like
``DeviceActivityDay``'s unselected rows). Never key material, digests or addresses:

- ``KnownDevice``: the coarse label and when it was created, last verified, forgotten;
- ``WebAuthnCredential``: the passkey's name and when it was created and last used;
- ``KnownNetwork``: only the granularity and the first/last-seen dates (a count of networks).
"""

from apps.backup.capture_managers import every_row

FIELDS = {
    "accounts.KnownDevice": ("id", "ua_label", "created_at", "last_verified_at", "revoked_at"),
    "accounts.WebAuthnCredential": ("id", "name", "created_at", "last_used_at"),
    "accounts.KnownNetwork": ("granularity", "created_at", "last_seen"),
}


def security_subject_query(model, user):
    """Only the person's own rows: a merged shell's sign-in memory is not carried over."""
    return every_row(model).filter(user_id=user.pk)
