"""Source-local notification authority is never portable or auto-reactivated."""

FIELD_NAMES = {
    "integrations.ChannelConfiguration": frozenset("id makerspace channel enabled room_enabled personal_enabled email_fallback provider integration_identity generation credentials quotas usage updated_at use_platform_sender sender_key credential_version activation_hold".split()),
    "integrations.NotificationEndpoint": frozenset("id makerspace user channel provider destination provider_subject identity_digest configuration integration_identity integration_generation verification_state verified_at consented_at consent_version revoked_at last_inbound_at created_at".split()),
    "integrations.NotificationEndpointChallenge": frozenset("id makerspace user configuration integration_generation integration_identity endpoint code_digest expires_at consumed_at attempts consented_at consent_version candidate_destination created_at".split()),
    "integrations.WhatsAppTemplate": frozenset("id configuration event audience locale template_name variables approved feature provider_identity validation_schema needs_review".split()),
    "integrations.NotificationEnvelope": frozenset("id makerspace feature stream event audience recipient subject_type subject_id scope context routing_snapshot message_body source_kind source_id revision dedup_key timing_policy mandatory available_at processed_at created_at".split()),
    "integrations.NotificationDelivery": frozenset("id makerspace envelope channel endpoint target_key provider integration_generation integration_identity state provider_id attempt_count ambiguous_count next_attempt_at last_error retryable claim_until created_at updated_at sender_key provider_source credential_version recipient_phone_hash recipient_alias_hash estimated_segments billed_segments quota_reserved_at historical accepted_at sent_at delivered_at read_at failed_at".split()),
    "integrations.NotificationMediaGrant": frozenset("id delivery document token_digest expires_at consumed_at".split()),
    "notifications.NotificationPreference": frozenset("id makerspace user category channels email_fallback updated_at".split()),
    "integrations.NotificationCutover": frozenset("id route sending_enabled barrier_at receipt_watermark replay_watermark snapshot copied_at reconciled_at activated_at".split()),
    "integrations.NotificationIngress": frozenset("id signed_user configuration makerspace makerspace_reference configuration_reference channel provider transport sender_key generation credential_version integration_identity dedupe_key payload protection_applied state attempts next_attempt_at last_error received_at processed_at".split()),
    "integrations.NotificationLegacyMapping": frozenset("id legacy_model legacy_id canonical_model canonical_id makerspace disposition snapshot created_at".split()),
    "integrations.NotificationCredentialVersion": frozenset("id configuration configuration_reference makerspace_reference generation provider integration_identity sender_key credentials retired_at wiped_at".split()),
    "integrations.NotificationProviderReference": frozenset("id provider sender_key provider_id phone_hash delivery_reference makerspace_reference generation attempt ambiguous created_at".split()),
}
OMITTED_MODELS = {label: "Source-local notification credentials, proof, policy or delivery telemetry; target reconnects with fresh consent."
                  for label in FIELD_NAMES if label != "notifications.NotificationPreference"}
USER_FIELDS = frozenset({
    ("integrations.NotificationEnvelope", "recipient"),
    ("integrations.NotificationEndpoint", "user"),
    ("integrations.NotificationEndpointChallenge", "user"),
    ("notifications.NotificationPreference", "user"),
    ("integrations.NotificationIngress", "signed_user"),
})

# Raw *_reference, encrypted payload/snapshot and sender hashes above are
# source-deployment correlation/protection. DROP never remaps or imports them;
# deleting a tenant must retain retired verifiers, ingress and physical STOP.
