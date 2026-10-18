"""Minimal personal notice rendering; F/G persist/deliver envelopes after commit.

The durable work item contains event/member/application IDs and version only.
Never pass answers, contact fields, review text, invite tokens or payment QR here.
"""
from urllib.parse import urlsplit

MESSAGES = {
    "application_submitted": ("Application received", "Your application has been submitted for review."),
    "application_offered": ("A hackathon place is offered", "Review your offer and RSVP before its deadline. An offer is confirmed only after RSVP succeeds."),
    "application_waitlisted": ("You are on the waitlist", "Your application is on the event waitlist. We will notify you when a place is offered."),
    "application_rejected": ("Application decision available", "The event team has completed its review. Open your application to see its decision."),
    "application_confirmed": ("Your place is confirmed", "Your RSVP succeeded. Open the event for your registration and next steps."),
    "application_declined": ("Offer declined", "Your offer has been declined and its reservation released."),
    "application_expired": ("RSVP deadline passed", "Your offer has expired and its reservation has been released."),
    "application_withdrawn": ("Application withdrawn", "Your application has been withdrawn. Existing payment and refund rules still apply."),
    "rsvp_extended": ("RSVP deadline updated", "The event team updated your RSVP deadline. Review the current deadline in your application."),
    "team_eligibility_changed": ("Team eligibility changed", "A roster member's eligibility changed. Review the team's current status before submitting."),
    "event_cancelled": ("Event cancelled", "The event has been cancelled. Open your registration for the current status and any payment information."),
}


def render_notice(*, kind, application_url):
    """G passes its configured same-origin member route, never an untrusted URL."""
    parsed = urlsplit(application_url)
    if not application_url.startswith("/") or application_url.startswith("//") or parsed.scheme or parsed.netloc:
        raise ValueError("Admission notice links must be a local member path.")
    title, body = MESSAGES[kind]
    return {"title": title, "body": body, "action_label": "Open application", "action_url": application_url}
