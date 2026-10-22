"""Source-local notification authority is never portable or auto-reactivated."""

FIELD_NAMES = {
    "integrations.ChannelConfiguration": frozenset("id makerspace channel enabled room_enabled personal_enabled email_fallback provider integration_identity generation credentials quotas usage updated_at".split()),
    "integrations.NotificationEndpoint": frozenset("id makerspace user channel provider destination provider_subject identity_digest configuration integration_identity integration_generation verification_state verified_at consented_at consent_version revoked_at last_inbound_at created_at".split()),
    "integrations.NotificationEndpointChallenge": frozenset("id makerspace user configuration integration_generation integration_identity endpoint code_digest expires_at consumed_at attempts consented_at consent_version candidate_destination created_at".split()),
    "integrations.WhatsAppTemplate": frozenset("id configuration event audience locale template_name variables approved".split()),
    "integrations.NotificationEnvelope": frozenset("id makerspace feature stream event audience recipient subject_type subject_id scope context routing_snapshot message_body source_kind source_id revision dedup_key timing_policy mandatory available_at processed_at created_at".split()),
    "integrations.NotificationDelivery": frozenset("id makerspace envelope channel endpoint target_key provider integration_generation integration_identity state provider_id attempt_count ambiguous_count next_attempt_at last_error retryable claim_until created_at updated_at".split()),
    "integrations.NotificationMediaGrant": frozenset("id delivery document certificate storage_makerspace source_revision recipient_id_snapshot integration_generation integration_identity token_digest expires_at consumed_at".split()),
    "notifications.NotificationPreference": frozenset("id makerspace user category channels email_fallback updated_at".split()),
}
OMITTED_MODELS = {label: "Source-local notification credentials, proof, policy or delivery telemetry; target reconnects with fresh consent."
                  for label in FIELD_NAMES if label != "notifications.NotificationPreference"}
USER_FIELDS = frozenset({
    ("integrations.NotificationEnvelope", "recipient"),
    ("integrations.NotificationEndpoint", "user"),
    ("integrations.NotificationEndpointChallenge", "user"),
    ("notifications.NotificationPreference", "user"),
})
