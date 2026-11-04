"""Phase 2 bookings retention snapshot: decision reasons, departures, issues, place photos.

All of it is tenant history that travels with a portable dump:

* `Booking.decision_reason` / `departed_at` are historical facts about the reservation;
* `BookingDepartureEvent` is append-only evidence (its remark is scoped PII, re-encrypted
  for the target like every other registered field) and `BookingIssue` is its triage row;
* `BookableSpacePhoto.object_key` names a PUBLIC image whose bytes the verified object
  journal copies, allocating a collision-safe key on the target.

User edges (`actor`, `resolved_by`, `uploaded_by`) are ordinary relational references.
Nothing here is a credential or a source of target authority.
"""

FIELD_NAMES = {
    "bookings.BookableSpacePhoto": frozenset(
        "id space object_key size_bytes caption position uploaded_by created_at".split()),
    "bookings.BookingDepartureEvent": frozenset(
        "id makerspace booking actor outcome remark source recorded_at".split()),
    "bookings.BookingIssue": frozenset(
        "id makerspace booking departure outcome created_at resolved_at resolved_by resolution_note".split()),
}
BOOKING_EXTRA_FIELDS = frozenset({"decision_reason", "departed_at"})
EXPORTED_FIELDS = {label: " ".join(sorted(names)) for label, names in FIELD_NAMES.items()}

DATASETS = {
    "bookings.BookableSpacePhoto": ("bookings/space_photos.csv", ("space__makerspace",)),
    "bookings.BookingDepartureEvent": ("bookings/departure_history.csv", ("makerspace",)),
    "bookings.BookingIssue": ("bookings/issues.csv", ("makerspace",)),
}
SUBJECT_PATHS = {
    "bookings.BookingDepartureEvent": ("booking__member",),
    "bookings.BookingIssue": ("booking__member",),
}
USER_EDGES = frozenset({
    ("bookings.BookableSpacePhoto", "uploaded_by"),
    ("bookings.BookingDepartureEvent", "actor"),
    ("bookings.BookingIssue", "resolved_by"),
})


def authority_entries(authority, disposition):
    return (
        (("bookings.Booking", "departed_at"),
         authority(disposition.PRESERVE, "Departure is a historical fact, independent of later lifecycle.")),
        (("bookings.BookingIssue", "resolved_at"),
         authority(disposition.PRESERVE, "Issue triage history; target staff may reopen nothing, only resolve open rows.")),
    )


def unique_rules(preserve, remap, policy):
    def photo_key(row, target, source_value):
        raise RuntimeError("Space photo collision escaped the verified import object journal.")

    photo_key.refuses_collision = True
    return {
        ("bookings.BookableSpacePhoto", "field:object_key"): policy(
            preserve, "Verified object journal allocates collision-safe public image keys.",
            field="object_key", generator=photo_key),
        ("bookings.BookingIssue", "field:departure"): policy(
            remap, "One issue per departure event; follows the imported event."),
    }
