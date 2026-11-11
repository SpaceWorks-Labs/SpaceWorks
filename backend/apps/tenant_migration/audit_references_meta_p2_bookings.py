"""Phase 2 bookings audit metadata id references for portable tenant archives."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

P2_BOOKING_AUDIT_EDGES = {
    # Gallery photos are deletable; all immutable history is source provenance.
    ("booking.space_photo_added", "photo_id"): AuditReference(S, "bookings.BookableSpacePhoto"),
    ("booking.space_photo_updated", "photo_id"): AuditReference(S, "bookings.BookableSpacePhoto"),
    ("booking.space_photo_removed", "photo_id"): AuditReference(S, "bookings.BookableSpacePhoto"),
    ("booking.departure_recorded", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("booking.departure_recorded", "issue_id"): AuditReference(R, "bookings.BookingIssue"),
    ("booking.issue_resolved", "issue_id"): AuditReference(R, "bookings.BookingIssue"),
    ("booking.issue_resolved", "booking_id"): AuditReference(R, "bookings.Booking"),
    # Decision 216: both bookings travel with the space.
    ("booking.replacement_created", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("booking.replacement_created", "replaces_booking_id"): AuditReference(R, "bookings.Booking"),
    # Decision 221(d): the per-term included-hours ledger entries.
    ("booking.included_hours_consumed", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("booking.included_hours_restored", "booking_id"): AuditReference(R, "bookings.Booking"),
    # B13: the organization hours bank. The organization is deployment-global and never travels.
    ("booking.org_hours_consumed", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("booking.org_hours_consumed", "organization_id"): AuditReference(S, "organizations.Organization"),
    ("booking.org_hours_released", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("booking.org_hours_released", "organization_id"): AuditReference(S, "organizations.Organization"),
    ("organization.hours_allowance_updated", "organization_id"): AuditReference(S, "organizations.Organization"),
    ("organization.hours_adjusted", "organization_id"): AuditReference(S, "organizations.Organization"),
}
