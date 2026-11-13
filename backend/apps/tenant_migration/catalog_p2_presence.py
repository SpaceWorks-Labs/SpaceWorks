"""Ephemeral presence and source display consent never become target authority."""
FIELD_NAMES = {
    "presence.PresenceSession": frozenset("id member account makerspace membership started_at expires_at ended_at ended_by end_reason created_via_claim_session status project account_project event_registration hide_on_display revision expiry_reminded_at".split()),
    "presence.PresenceSettings": frozenset("id makerspace show_names allow_personal_opt_out display_version".split()),
    "presence.PresencePreference": frozenset("id makerspace account hide_on_display".split()),
}
DROP_MODELS = {label: "Source-local live presence or display consent; fresh target check-in and privacy configuration required."
                  for label in FIELD_NAMES}
# A paired wall display carries its device token digest and is re-paired on the target: never portable, so it is
# outside FIELD_NAMES (which are scanned/exported) and only appears in the field snapshot and data_export omissions.
OMITTED_FIELD_NAMES = {
    "presence.DisplayScreen": frozenset("id makerspace token_digest pairing_code code_expires_at name panels rotation_seconds announcement config_version created_at claimed_at revoked_at last_seen_at layout theme privacy refresh_seconds slide_seconds link_secret_enc players".split()),
    "presence.AnthiasPlayer": frozenset("id makerspace name host_url username password_enc api_version anthias_version status last_error last_synced_at created_at screens".split()),
    "presence.AnthiasAssetLink": frozenset("id player display asset_id synced_hash uri_hash".split()),
    "presence.SpaceNowConfig": frozenset("id makerspace sections privacy refresh_seconds updated_at".split()),
}
OMITTED_MODELS = {
    "presence.DisplayScreen": "Paired wall display with a device token digest; the target space pairs its own screens.",
    "presence.AnthiasPlayer": "Holds an encrypted player credential and a LAN address; the target space registers its own players.",
    "presence.AnthiasAssetLink": "Maps a source screen to an asset id on a source player; meaningless on the target.",
    "presence.SpaceNowConfig": "Layout of the public page on the source; the target space chooses its own.",
}
EXPORTED_FIELDS = {label: " ".join(sorted(fields)) for label, fields in FIELD_NAMES.items()}
USER_FIELDS = frozenset({("presence.PresenceSession", "account"), ("presence.PresencePreference", "account")})


def classify(exports):
    exports.update(EXPORTED_FIELDS)


def model_catalog(projected):
    return projected - FIELD_NAMES.keys()


def gate_tasks(internal, fanout):
    internal["apps.presence.tasks_anthias.sync_anthias_player_task"] = "Writes player status inside tenant_write for one space."
    internal["apps.presence.tasks.expire_presence_sessions_task"] = "Expiry and reminder outbox writes gate every tenant separately."
    fanout["apps.presence.tasks.sweep_presence"] = "Presence expiry and reminder envelopes use fanout_tenant_write."
