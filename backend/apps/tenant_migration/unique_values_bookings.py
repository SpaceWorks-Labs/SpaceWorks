"""Source-local booking outbox relations never become target send authority."""
from .unique_values_policy import NULL, _policy

BOOKING_UNIQUE_RULES = {
    ("bookings.BookingBroadcastDelivery", "field:outbox"): _policy(
        NULL, "The source outbox relation is omitted and reconstructed as null."),
}
