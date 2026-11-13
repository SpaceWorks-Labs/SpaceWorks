"""Only the four explicitly authorized values may cross into the PDF engine."""
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.operations.printable_layout import page_layout
from apps.operations.printable_pdf import render_sheet
from .pass_templates import PASS_FIELDS, normalize_pass_template


def pass_values(booking):
    zone = ZoneInfo(booking.space.makerspace.timezone)
    window = " - ".join(timezone.localtime(value, zone).strftime("%d %b %Y %H:%M %Z")
                        for value in (booking.starts_at, booking.ends_at))
    # Booking.name uses its existing encrypted model accessor. Never inspect the
    # answer snapshot, notes, contacts, public token or check-in credential here.
    return {"name": booking.name, "resource": booking.space.name,
            "booking_window": window, "reference": f"Booking #{booking.pk}"}


def render_pass(template, values):
    template = normalize_pass_template(template)
    safe = {field: values[field] for field in PASS_FIELDS}
    return render_sheet(template, [safe], title="Booking pass", layout=page_layout)


def sample_values():
    return {"name": "Sample booker", "resource": "Sample resource",
            "booking_window": "15 Oct 2026 10:00 - 15 Oct 2026 11:00",
            "reference": "Booking #123"}
