"""Departure revokes resource authority even for accounts without memberships."""

from apps.accounts.account_deletion_discovery import _model
from apps.audit import services as audit
from apps.backup.capture_managers import every_row


def revoke_resource_grants(user, now):
    # Stage A already holds ascending Makerspaces -> Organizations -> User.
    # Domain grant writers take their tenant lock first too; no domain/tenant
    # lock may be acquired after these credential rows.
    for label, prefix in (
        ("events.EventStaffGrant", "event"),
        ("bookings.BookingSpaceStaffGrant", "booking"),
    ):
        model = _model(label)
        if model is None:
            continue
        for row in every_row(model).select_for_update().filter(
            user=user, revoked_at__isnull=True,
        ).order_by("makerspace_id", "pk"):
            row.revoked_at, row.revoked_by = now, user
            row.save(update_fields=["revoked_at", "revoked_by"])
            audit.record(user, f"{prefix}.staff_grant_revoked", makerspace=row.makerspace,
                         target=row, meta={"permissions": row.permissions, "reason": "account_deletion"})
