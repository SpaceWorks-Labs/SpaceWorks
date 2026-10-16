"""Phase 2 bookings staff routes keyed by a space/issue primary key (origin scoping)."""

MODEL_LOOKUPS = {
    **{name: ("bookings.BookableSpace", "makerspace_id") for name in (
        "admin-bookable-space-photos", "admin-bookable-space-photo-presign",
        "admin-bookable-space-photo-order", "admin-bookable-space-photo", "admin-booking-arrival-depart",
    )},
    "admin-booking-issue-resolve": ("bookings.BookingIssue", "makerspace_id"),
}
