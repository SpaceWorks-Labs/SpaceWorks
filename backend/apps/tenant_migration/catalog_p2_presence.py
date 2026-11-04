"""Ephemeral presence and source display consent never become target authority."""
FIELD_NAMES = {
    "presence.PresenceSession": frozenset("id member account makerspace membership started_at expires_at ended_at ended_by end_reason created_via_claim_session status project event_registration hide_on_display revision expiry_reminded_at".split()),
    "presence.PresenceSettings": frozenset("id makerspace show_names allow_personal_opt_out display_version".split()),
    "presence.PresencePreference": frozenset("id makerspace account hide_on_display".split()),
}
DROP_MODELS = {label: "Source-local live presence or display consent; fresh target check-in and privacy configuration required."
                  for label in FIELD_NAMES}
EXPORTED_FIELDS = {label: " ".join(sorted(fields)) for label, fields in FIELD_NAMES.items()}
USER_FIELDS = frozenset({("presence.PresenceSession", "account"), ("presence.PresencePreference", "account")})


def classify(exports):
    exports.update(EXPORTED_FIELDS)


def model_catalog(projected):
    return projected - FIELD_NAMES.keys()


def gate_tasks(internal, fanout):
    internal["apps.presence.tasks.expire_presence_sessions_task"] = "Expiry and reminder outbox writes gate every tenant separately."
    fanout["apps.presence.tasks.sweep_presence"] = "Presence expiry and reminder envelopes use fanout_tenant_write."
