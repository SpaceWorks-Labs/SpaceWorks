"""Deletion fences for approved portable identities, outside the user projection."""

import json

LIFECYCLE_PATH = "global/user_lifecycle.json"
LIFECYCLE_FIELDS = (
    "deletion_requested_at", "deletion_purge_after", "purge_started_at", "account_purged_at",
)


def write_user_lifecycle(root, users):
    """Receive only the closure remaining after portable disclosure approval.

    Active identities disclose no extra account state. Deleted identities need these
    fences so importing retained history cannot reactivate them or restart erasure.
    The migration envelope hashes this file alongside every other payload member.
    """
    records = {}
    for user in users:
        values = {name: getattr(user, name) for name in LIFECYCLE_FIELDS}
        if any(values.values()):
            records[str(user.pk)] = {
                name: value.isoformat() if value else "" for name, value in values.items()
            }
    if records:
        path = root / LIFECYCLE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(records, sort_keys=True, separators=(",", ":")), encoding="utf-8",
        )
