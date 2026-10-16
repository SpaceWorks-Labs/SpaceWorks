"""Phase 2 bookings audit metadata id references for portable tenant archives."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

P2_BOOKING_AUDIT_EDGES = {
    ("booking.space_photo_added", "photo_id"): AuditReference(R, "bookings.BookableSpacePhoto"),
    ("booking.space_photo_updated", "photo_id"): AuditReference(R, "bookings.BookableSpacePhoto"),
    # The removed photo row no longer exists: inert source provenance.
    ("booking.space_photo_removed", "photo_id"): AuditReference(S, "bookings.BookableSpacePhoto"),
    ("booking.departure_recorded", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("booking.departure_recorded", "issue_id"): AuditReference(R, "bookings.BookingIssue"),
    ("booking.issue_resolved", "issue_id"): AuditReference(R, "bookings.BookingIssue"),
    ("booking.issue_resolved", "booking_id"): AuditReference(R, "bookings.Booking"),
}
