"""Events programme vocabulary; source adapters must still prove live delivery eligibility."""

PROGRAMME_EVENTS = (
    "application_submitted", "application_offered", "application_waitlisted",
    "application_rejected", "application_confirmed", "application_declined",
    "application_expired", "application_withdrawn", "rsvp_extended",
    "team_eligibility_changed", "event_cancelled", "certificate_ready", "certificate_revoked",
    # Release 2 L2 (G7, G9): organiser digest, member removal/ticket notices, mentor room alert.
    "approval_digest", "registration_removed", "ticket_resent", "mentor_help_alert",
    # r2-idcards-best C4: a certificate design waits for its signatory's approval.
    "certificate_signature_requested",
)
