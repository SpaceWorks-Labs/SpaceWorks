"""Analytics views: bookable rooms and resources, and their bookings. No names, emails,
phones, notes, answers or check-in tokens: a booking is its member id, times and state."""

from .types import Col, View

D = "bookings"
_MINUTES = "round((extract(epoch FROM b.ends_at - b.starts_at) / 60.0)::numeric, 1)"

VIEWS = (
    View("bookable_spaces", D, "Rooms and resources that can be booked.",
         "FROM {bookings.BookableSpace} s", "s.makerspace_id", (
             Col("bookable_space_id", "s.id", "Resource id."),
             Col("name", "s.name", "Resource name."),
             Col("kind", "s.kind", "Room, desk, machine time and so on."),
             Col("capacity", "s.capacity", "Capacity."),
             Col("machine_type_id", "s.machine_type_id", "Machine type, for machine time (machine_types)."),
             Col("machine_id", "s.machine_id", "Machine, for machine time (machines)."),
             Col("payment_amount", "s.payment_amount", "Price per booking."),
             Col("is_public", "s.is_public", "Bookable from the public page."),
             Col("is_active", "s.is_active", "Open for booking."),
             Col("created_at", "s.created_at", "Added."),
         )),
    View("bookings", D, "Bookings with their times and state.",
         "FROM {bookings.Booking} b JOIN {bookings.BookableSpace} s ON s.id = b.space_id", "s.makerspace_id", (
             Col("booking_id", "b.id", "Booking id."),
             Col("bookable_space_id", "b.space_id", "Resource (bookable_spaces)."),
             Col("member_id", "b.member_id", "Member (members); empty for a guest booking."),
             Col("status", "b.status", "Booking state."),
             Col("starts_at", "b.starts_at", "Starts."),
             Col("ends_at", "b.ends_at", "Ends."),
             Col("duration_minutes", _MINUTES, "Booked minutes."),
             Col("created_at", "b.created_at", "Requested."),
             Col("cancelled_at", "b.cancelled_at", "Cancelled."),
             Col("arrived_at", "b.arrived_at", "Checked in."),
             Col("departed_at", "b.departed_at", "Checked out."),
         )),
)
