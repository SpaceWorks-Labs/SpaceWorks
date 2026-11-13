"""Events programme vocabulary; source adapters must still prove live delivery eligibility."""

MENTOR_HELP_PERSONAL_EVENT = "mentor_help_update"
MENTOR_HELP_SOURCE = "events.mentor_help"
MENTOR_WHATSAPP_MARKER = "mentor_whatsapp_policy"
MENTOR_WHATSAPP_VERSION = "created_v1"

PROGRAMME_EVENTS = (
    "application_submitted", "application_offered", "application_waitlisted",
    "application_rejected", "application_confirmed", "application_declined",
    "application_expired", "application_withdrawn", "rsvp_extended",
    "team_eligibility_changed", "event_cancelled", "certificate_ready", "certificate_revoked",
    # Release 2 L2 (G7, G9): organiser digest, member removal/ticket notices, mentor room alert.
    "approval_digest", "registration_removed", "ticket_resent", "mentor_help_alert", MENTOR_HELP_PERSONAL_EVENT,
    # r2-idcards-best C4: a certificate design waits for its signatory's approval.
    "certificate_signature_requested",
    # Decision 301 (hackathon review): team notices, registered so they are delivered and show in the inbox.
    "team_invited", "team_join_requested", "team_join_declined", "team_membership_updated", "team_reopened",
    "team_disbanded", "team_leadership_transferred", "team_member_removed",
)
