"""Already-authorized owner projection; no contacts, notes or answer snapshots."""
from zoneinfo import ZoneInfo
from django.utils import timezone
from apps.makerspaces.confirmation_render import google_calendar_url, render_confirmation_png
from apps.makerspaces.platform import feature_enabled
from .services_arrival import qr_value
from .services_schedule import member_can_cancel, cancellation_cutoff


def qr_available(booking, *, now=None):
    return (feature_enabled(booking.space.makerspace, "bookings.checkin")
            and booking.status == "confirmed" and booking.space.is_active
            and booking.ends_at >= (now or timezone.now()))


def confirmation_data(booking):
    space = booking.space
    return {
        "public_token": booking.public_token, "space_name": space.name,
        "timezone": space.makerspace.timezone, "starts_at": booking.starts_at,
        "ends_at": booking.ends_at, "status": booking.status, "location": space.location,
        "description": space.description, "arrived_at": booking.arrived_at,
        "can_cancel": booking.arrived_at is None and member_can_cancel(booking, now=timezone.now()),
        "cancellation_cutoff_at": cancellation_cutoff(booking),
        "qr_value": qr_value(booking) if qr_available(booking) else None,
        "google_calendar_url": google_calendar_url(title=space.name, starts_at=booking.starts_at,
            ends_at=booking.ends_at, location=space.location),
    }


def confirmation_png(booking):
    zone = ZoneInfo(booking.space.makerspace.timezone)
    window = tuple(timezone.localtime(value, zone).strftime("%d %b %Y %H:%M %Z")
                   for value in (booking.starts_at, booking.ends_at))
    return render_confirmation_png(qr_value=qr_value(booking), title=booking.space.name,
                                   lines=(*window, booking.status, booking.space.location))
