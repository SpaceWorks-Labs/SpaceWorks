"""Literal authority pins for the lanes merged into the integration branch.

Bookings/events websites, booking check-in and cancellation provenance, broadcasts,
email provenance, digest defaults and the Phase 1 public profile contract.
"""
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D

_KEEP = (D.PRESERVE,)
_RESET = (D.RESET,)
_DROP = (D.DROP,)
_CONDITIONAL = (D.PRESERVE, D.RESET)  # History travels; live sends are reset.
_AUTHORED = (D.PRESERVE, D.DROP)  # Full users keep authored content; stubs drop it.


def _pins(label, names, dispositions):
    return {(label, name): dispositions for name in names.split()}


MERGED_EXPECTED = {
    # Bookings
    **_pins("bookings.BookableSpace", "pass_template", _KEEP),
    **_pins("bookings.Booking", "arrived_at cancelled_at status_before_cancel", _KEEP),
    **_pins("bookings.Booking", "checkin_token", _RESET),
    **_pins("bookings.BookingBroadcast", "recipient_cursor recipients_complete status", _CONDITIONAL),
    **_pins("bookings.BookingBroadcastDelivery", "outbox status", _CONDITIONAL),
    **_pins("bookings.BookingResourcePage", "released", _RESET),
    **_pins("bookings.BookingResourcePageSection", "visibility", _KEEP),
    # Events
    **_pins("events.Event", "organization_admission_blocked", _RESET),
    **_pins("events.Event", "show_registration_count", _KEEP),
    **_pins("events.EventSeries", "organization_admission_blocked", _RESET),
    **_pins("events.EventAttendanceCertificate", "layout_snapshot", _RESET),
    **_pins("events.EventCertificateArtwork", "version_id", _RESET),
    **_pins("events.EventBroadcast", "recipient_cursor recipients_complete status", _CONDITIONAL),
    **_pins("events.EventBroadcastDelivery", "outbox status", _CONDITIONAL),
    **_pins("events.EventPage", "released", _RESET),
    **_pins("events.EventPage", "section_enabled", _KEEP),
    **_pins("events.EventPageSection", "visibility", _KEEP),
    **_pins("events.EventSession", "visibility", _KEEP),
    **_pins("events.EventRegistration", "cancelled_at status_before_cancel waitlist_position_at", _KEEP),
    # Notifications and email provenance
    **_pins("integrations.EmailLog", "source_id source_kind source_metadata", _DROP),
    **_pins("integrations.NotificationTimingPolicy", "daily_digest_default", _DROP),
    # Makerspace website and event defaults
    **_pins("makerspaces.Makerspace", "event_default_registration_audience", _KEEP),
    **_pins("makerspaces.Makerspace", "website_embed_origins", _RESET),
    # Public profile contract: disclosure resets, authored content and handles travel.
    **_pins("makerspaces.MemberProfile", "public_consented_at public_visible show_activity_graph "
            "show_bookings show_events show_loans show_machine_activity show_projects show_speaking", _RESET),
    **_pins("makerspaces.MemberProfile", "domains links skills", _AUTHORED),
    **_pins("makerspaces.MemberProject", "public_visible", _RESET),
    **_pins("makerspaces.MemberProject", "subtitle tags", _AUTHORED),
    **_pins("makerspaces.ProfileTimelineEntry",
            "id profile kind title organization location start end description order", _AUTHORED),
    **_pins("makerspaces.PublicHandle", "id user profile handle claimed_at changed_at", _AUTHORED),
}
