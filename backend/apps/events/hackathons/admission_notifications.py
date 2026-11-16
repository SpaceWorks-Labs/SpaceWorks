"""Minimal personal notice rendering; F/G persist/deliver envelopes after commit.

The durable work item contains event/member/application IDs and version only.
Never pass answers, contact fields, review text, invite tokens or payment QR here.
"""
from urllib.parse import urlsplit

from django.utils.translation import gettext, gettext_noop as _

MESSAGES = {
    "application_submitted": (_("Application received"), _("Your application has been submitted for review.")),
    "application_offered": (_("A hackathon place is offered"), _("Review your offer and RSVP before its deadline. An offer is confirmed only after RSVP succeeds.")),
    "application_waitlisted": (_("You are on the waitlist"), _("Your application is on the event waitlist. We will notify you when a place is offered.")),
    "application_rejected": (_("Application decision available"), _("The event team has completed its review. Open your application to see its decision.")),
    "application_confirmed": (_("Your place is confirmed"), _("Your RSVP succeeded. Open the event for your registration and next steps.")),
    "application_declined": (_("Offer declined"), _("Your offer has been declined and its reservation released.")),
    "application_expired": (_("RSVP deadline passed"), _("Your offer has expired and its reservation has been released.")),
    "application_withdrawn": (_("Application withdrawn"), _("Your application has been withdrawn. Existing payment and refund rules still apply.")),
    "rsvp_extended": (_("RSVP deadline updated"), _("The event team updated your RSVP deadline. Review the current deadline in your application.")),
    "team_eligibility_changed": (_("Team eligibility changed"), _("A roster member's eligibility changed. Review the team's current status before submitting.")),
    "event_cancelled": (_("Event cancelled"), _("The event has been cancelled. Open your registration for the current status and any payment information.")),
}


def render_notice(*, kind, application_url):
    """G passes its configured same-origin member route, never an untrusted URL."""
    parsed = urlsplit(application_url)
    if not application_url.startswith("/") or application_url.startswith("//") or parsed.scheme or parsed.netloc:
        raise ValueError("Admission notice links must be a local member path.")
    title, body = MESSAGES[kind]
    # Translated at render time: the outbox calls a lazy renderer in the recipient's language (decision 296).
    return {"title": gettext(title), "body": gettext(body), "action_label": gettext("Open application"),
            "action_url": application_url}
