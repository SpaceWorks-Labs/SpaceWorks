"""Arrival facts travel; disclosure credentials are regenerated on the target."""
FIELD_NAMES = {"bookings.BookingCheckInEvent": frozenset("id booking actor action source recorded_at".split())}


def authority_entries(authority, disposition):
    return (
        (("bookings.Booking", "checkin_token"), authority(disposition.RESET, "Never reuse source arrival credentials.")),
        (("bookings.Booking", "arrived_at"), authority(disposition.PRESERVE, "Current arrival is a historical fact, independent of completion.")),
    )
