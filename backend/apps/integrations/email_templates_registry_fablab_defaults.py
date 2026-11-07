"""Authored default bodies for the events/bookings/maintenance/membership streams.

Separated from the registry module for the same reason the hardware/printing defaults
are: strings are bulk, structure is not, and mixing them puts both past the file ceiling.

Two rules these defaults follow, and a reader changing them should keep:

* **A staff default reproduces what the adapter sends today.** The four adapters built
  their bodies inline in Python; moving that wording here verbatim is what makes the
  switch to the template path a no-op for a space that never edits one.
* **A requester default never contains staff-only detail.** Requester wording addresses
  the person the notification is about, and it is the body a member reads — so no other
  member's name, no internal ids beyond their own, no staff notes.
"""
from django.utils.translation import gettext_noop

# --- events ---------------------------------------------------------------------------

EVENTS_STAFF_SUBJECT = gettext_noop("{{ makerspace.name }} event #{{ event.id }} {{ event_name }}")
EVENTS_STAFF_TEXT = gettext_noop("""Event #{{ event.id }} {{ event_name }}.
Title: {{ event.title }}
Time: {{ event.when }}
Status: {{ event.status }}
{% if event.location %}Location: {{ event.location }}
{% endif %}{% if registration %}Registration: #{{ registration.id }}
Registrant: {{ registration.name }}
Registration status: {{ registration.status }}
{% endif %}""")

EVENTS_REQUESTER_SUBJECTS = {
    "published": gettext_noop("{{ event.title }} is open for registration"),
    "cancelled": gettext_noop("{{ event.title }} has been cancelled"),
    "completed": gettext_noop("Thank you for attending {{ event.title }}"),
    "registration_created": gettext_noop("You are registered for {{ event.title }}"),
    "registration_pending_approval": gettext_noop("Your application for {{ event.title }} is awaiting approval"),
    "registration_waitlisted": gettext_noop("You are on the waitlist for {{ event.title }}"),
    "registration_approved": gettext_noop("Your application for {{ event.title }} was approved"),
    "registration_rejected": gettext_noop("Your application for {{ event.title }} was not approved"),
    "registration_cancelled": gettext_noop("Your registration for {{ event.title }} was cancelled"),
    "registration_restored": gettext_noop("Your registration for {{ event.title }} was restored"),
    "registration_promoted": gettext_noop("A place has opened up for {{ event.title }}"),
    "registration_attended": gettext_noop("Your attendance at {{ event.title }} is recorded"),
    "series_published": gettext_noop("{{ event.title }} recurring schedule published"),
    "series_cancelled": gettext_noop("{{ event.title }} recurring schedule cancelled"),
    "series_completed": gettext_noop("{{ event.title }} recurring schedule completed"),
    "series_generation_failed": gettext_noop("{{ event.title }} needs schedule attention"),
    "reminder": gettext_noop("Reminder: {{ event.title }} is coming up"),
}

EVENTS_REQUESTER_BODIES = {
    "published": gettext_noop("Registration is now open."),
    "cancelled": (
        gettext_noop("This event has been cancelled. Please contact the makerspace if you have "
        "questions.")
    ),
    "completed": gettext_noop("This event has finished. Thank you for taking part."),
    "registration_created": gettext_noop("Your place is booked. We look forward to seeing you."),
    "registration_pending_approval": (
        gettext_noop("Your application was received. No payment is due unless it is approved into "
        "a confirmed place.")
    ),
    "registration_waitlisted": (
        gettext_noop("Your registration is on the waiting list. No payment is due unless a place "
        "is confirmed.")
    ),
    "registration_approved": (
        gettext_noop("Your application was approved. The registration status above shows whether "
        "your place is confirmed or waitlisted.")
    ),
    "registration_rejected": (
        gettext_noop("Your application was not approved. You were not charged.")
    ),
    "registration_cancelled": (
        gettext_noop("Your registration has been cancelled. Contact the makerspace about any "
        "settled payment or registering again for a paid event.")
    ),
    "registration_promoted": (
        gettext_noop("You were on the waiting list and a place has opened up. Your registration is "
        "now confirmed.")
    ),
    "registration_attended": gettext_noop("Your attendance has been recorded."),
    "registration_restored": (
        gettext_noop("Your cancellation was undone. Your current registration status is shown above. "
        "Registered means your place is confirmed; waitlisted means you are in the queue; "
        "pending_approval means staff still need to approve your application.")
    ),
    "series_published": gettext_noop("The recurring schedule is now published."),
    "series_cancelled": gettext_noop("The recurring schedule has been cancelled."),
    "series_completed": gettext_noop("The recurring schedule is complete."),
    "series_generation_failed": gettext_noop("Automatic occurrence generation needs staff attention."),
    "reminder": gettext_noop("Your event is coming up. Please check the time and location above."),
}

EVENTS_REQUESTER_TEXT = gettext_noop("""Hello {{ registration.name|default:"there" }},

{{ makerspace.name }}
Event: {{ event.title }}
Time: {{ event.when }}
{% if event.location %}Location: {{ event.location }}
{% endif %}
{% if event_name == "registration_restored" %}Registration status: {{ registration.status }}
{% endif %}
{{ next_steps }}
""")

# --- bookings -------------------------------------------------------------------------

BOOKINGS_STAFF_SUBJECT = (
    gettext_noop("{{ makerspace.name }} booking #{{ booking.id }} {{ event_name }}")
)
BOOKINGS_STAFF_TEXT = gettext_noop("""Booking #{{ booking.id }} {{ event_name }}.
Space: {{ booking.space.name }}
Time: {{ booking.when }}
Status: {{ booking.status }}
Booker: {{ booking.name }}
{% if event_name == "restored" %}{{ next_steps }}
{% endif %}""")

BOOKINGS_REQUESTER_SUBJECT = (
    gettext_noop("Booking {% if event_name == 'restored' %}restored{% else %}{{ booking.status }}{% endif %}: "
    "{{ booking.space.name }}")
)

# Verbatim from `bookings.notifications._message`, which is the wording members receive
# today. Changing it here changes what every unedited space sends.
BOOKINGS_REQUESTER_BODIES = {
    "created": (
        gettext_noop("Your booking request was received. We will contact you if its status changes.")
    ),
    "confirmed": (
        gettext_noop("Your booking is confirmed. Please contact the makerspace if your plans change.")
    ),
    "rejected": (
        gettext_noop("Your request was not approved. Please contact the makerspace if you have "
        "questions.")
    ),
    "cancelled": gettext_noop("Your booking has been cancelled."),
    "restored": (
        gettext_noop("Your cancellation was undone. The current booking status and time are shown above. "
        "Confirmed means your reservation is booked; pending means staff still need to "
        "approve your request. Please check the time and contact the makerspace if your plans change.")
    ),
    "completed": gettext_noop("Your booking has been marked completed."),
    "no_show": gettext_noop("Your booking has been marked as a no-show."),
    "reminder": gettext_noop("Your booking is coming up. Please check the time and space above."),
}

BOOKINGS_REQUESTER_TEXT = gettext_noop("""Hello {{ booking.name }},

{{ makerspace.name }}
Space: {{ booking.space.name }}
Time: {{ booking.when }}
Status: {{ booking.status }}

{{ next_steps }}
""")

# --- maintenance ----------------------------------------------------------------------

MAINTENANCE_STAFF_SUBJECT = (
    gettext_noop("{{ makerspace.name }} maintenance {{ event_name }}: {{ machine.name }}")
)
MAINTENANCE_STAFF_TEXT = gettext_noop("""Maintenance {{ event_name }}.
Machine: {{ machine.name }}
{% if schedule %}Schedule: #{{ schedule.id }}
Description: {{ schedule.description }}
Next due: {{ schedule.next_due }}
Active: {{ schedule.is_active }}
{% endif %}{% if log %}Log: #{{ log.id }}
Summary: {{ log.summary }}
Performed at: {{ log.performed_at }}
{% if log.parts_note %}Parts note: {{ log.parts_note }}
{% endif %}{% endif %}""")

MAINTENANCE_REQUESTER_SUBJECTS = {
    "schedule_created": gettext_noop("Maintenance scheduled for {{ machine.name }}"),
    "schedule_updated": gettext_noop("Maintenance schedule changed for {{ machine.name }}"),
    "schedule_deactivated": gettext_noop("Maintenance schedule paused for {{ machine.name }}"),
    "schedule_completed": gettext_noop("Maintenance completed on {{ machine.name }}"),
    "logged": gettext_noop("Maintenance recorded on {{ machine.name }}"),
}

MAINTENANCE_REQUESTER_BODIES = {
    "schedule_created": (
        gettext_noop("Maintenance has been scheduled for this machine. It may be unavailable around "
        "the due date.")
    ),
    "schedule_updated": gettext_noop("The maintenance schedule for this machine has changed."),
    "schedule_deactivated": gettext_noop("Scheduled maintenance for this machine has been paused."),
    "schedule_completed": gettext_noop("Scheduled maintenance on this machine is complete."),
    "logged": gettext_noop("Maintenance work on this machine has been recorded."),
}

# Deliberately thinner than the staff body: a member is told the machine and what it
# means for them, never the internal schedule ids, parts notes or engineer summaries.
MAINTENANCE_REQUESTER_TEXT = gettext_noop("""Hello,

{{ makerspace.name }}
Machine: {{ machine.name }}
{% if schedule %}Next due: {{ schedule.next_due }}
{% endif %}
{{ next_steps }}
""")

# --- membership -----------------------------------------------------------------------

MEMBERSHIP_STAFF_SUBJECTS = {
    "request_pending": gettext_noop("{{ makerspace.name }}: membership request pending"),
    "member_joined": gettext_noop("{{ makerspace.name }}: member joined"),
}

MEMBERSHIP_STAFF_TEXTS = {
    "request_pending": (
        "Membership request #{{ request.id }} is pending. "
        "Applicant: {{ request.applicant }}."
    ),
    "member_joined": "Member joined: {{ member.username }}.",
}

MEMBERSHIP_REQUESTER_SUBJECTS = {
    "request_pending": gettext_noop("Your membership request at {{ makerspace.name }}"),
    "member_joined": gettext_noop("Welcome to {{ makerspace.name }}"),
}

MEMBERSHIP_REQUESTER_TEXTS = {
    "request_pending": """Hello {{ member.name|default:"there" }},

Your membership request at {{ makerspace.name }} has been received and is waiting for
review. We will be in touch once it has been looked at.
""",
    "member_joined": """Hello {{ member.name|default:"there" }},

Your membership at {{ makerspace.name }} is active. Welcome!
""",
}
