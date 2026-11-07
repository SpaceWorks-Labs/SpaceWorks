"""Literal concrete-or-M2M field snapshot for the Lane D catalog.

This file is intentionally source-controlled rather than derived at import time. A
schema edit must add the field here and give any authority/disclosure input an
override in tenant_dump_authority.py before the catalog guard will pass.
"""

from .tenant_dump_field_snapshot_core import FIRST_PARTY_FIELD_NAMES

from .catalog_7b import PRINTER_FIELD_NAMES

FIRST_PARTY_FIELD_NAMES.update(PRINTER_FIELD_NAMES)
from .catalog_broadcasts import FIELD_NAMES as BROADCAST_FIELDS
FIRST_PARTY_FIELD_NAMES.update(BROADCAST_FIELDS)
from .catalog_website import FIELD_NAMES as WEBSITE_FIELDS
FIRST_PARTY_FIELD_NAMES.update(WEBSITE_FIELDS)
FIRST_PARTY_FIELD_NAMES["makerspaces.Makerspace"] |= {"website_embed_origins"}
FIRST_PARTY_FIELD_NAMES["integrations.EmailLog"] |= {"source_kind", "source_id", "source_metadata"}

from .catalog_7c import LABEL_FIELD_NAMES

FIRST_PARTY_FIELD_NAMES.update(LABEL_FIELD_NAMES)

from .catalog_w7_events import extend_event_field_snapshot
extend_event_field_snapshot(FIRST_PARTY_FIELD_NAMES)
FIRST_PARTY_FIELD_NAMES["events.Event"] |= {"show_registration_count"}
FIRST_PARTY_FIELD_NAMES["events.EventRegistration"] |= {"cancelled_at", "status_before_cancel", "waitlist_position_at"}

from .catalog_wp3 import WP3_FIELD_NAMES, WP3_EXTRA_FIELDS
FIRST_PARTY_FIELD_NAMES.update(WP3_FIELD_NAMES)
for _label, _names in WP3_EXTRA_FIELDS.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names

from .catalog_booking_arrival import FIELD_NAMES as BOOKING_ARRIVAL_FIELDS
FIRST_PARTY_FIELD_NAMES.update(BOOKING_ARRIVAL_FIELDS)
FIRST_PARTY_FIELD_NAMES["bookings.Booking"] |= {"checkin_token", "arrived_at"}
from .catalog_p2_bookings import FIELD_NAMES as P2_BOOKING_FIELDS, BOOKING_EXTRA_FIELDS as P2_BOOKING_EXTRA
FIRST_PARTY_FIELD_NAMES.update(P2_BOOKING_FIELDS)
FIRST_PARTY_FIELD_NAMES["bookings.Booking"] |= P2_BOOKING_EXTRA
from .catalog_r2_l1 import FIELD_NAMES as R2_L1_FIELDS, EXTRA_FIELDS as R2_L1_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L1_FIELDS)
for _label, _names in R2_L1_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l5 import FIELD_NAMES as R2_L5_FIELDS, EXTRA_FIELDS as R2_L5_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L5_FIELDS)
for _label, _names in R2_L5_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l15 import FIELD_NAMES as R2_L15_FIELDS, EXTRA_FIELDS as R2_L15_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L15_FIELDS)
for _label, _names in R2_L15_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_l12 import FIELD_NAMES as L12_FIELDS, EXTRA_FIELDS as L12_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(L12_FIELDS)
for _label, _names in L12_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_l23 import FIELD_NAMES as L23_FIELDS, EXTRA_FIELDS as L23_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(L23_FIELDS)
for _label, _names in L23_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_l16 import FIELD_NAMES as L16_FIELDS  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(L16_FIELDS)

AUTO_CREATED_FIELD_NAMES = {
    'auth.Group_permissions': frozenset('group id permission'.split()),
    'accounts.User_groups': frozenset('group id user'.split()),
    'accounts.User_user_permissions': frozenset('id permission user'.split()),
}

THIRD_PARTY_FIELD_NAMES = {
    'admin.LogEntry': frozenset('action_flag action_time change_message content_type id object_id object_repr user'.split()),
    'auth.Permission': frozenset('codename content_type group id name user'.split()),
    'auth.Group': frozenset('id name permissions user'.split()),
    'axes.AccessFailureLog': frozenset('attempt_time http_accept id ip_address locked_out path_info user_agent username'.split()),
    'axes.AccessAttempt': frozenset('attempt_time failures_since_start get_data http_accept id ip_address path_info post_data user_agent username'.split()),
    'axes.AccessAttemptExpiration': frozenset('access_attempt expires_at'.split()),
    'axes.AccessLog': frozenset('attempt_time http_accept id ip_address logout_time path_info session_hash user_agent username'.split()),
    'contenttypes.ContentType': frozenset('app_label id model'.split()),
    'sessions.Session': frozenset('expire_date session_data session_key'.split()),
    'token_blacklist.OutstandingToken': frozenset('created_at expires_at id jti token user'.split()),
    'token_blacklist.BlacklistedToken': frozenset('blacklisted_at id token'.split()),
    'oauth2_provider.Application': frozenset('algorithm allowed_origins authorization_grant_type cimd_expires_at client_id client_secret client_type created hash_client_secret id name post_logout_redirect_uris redirect_uris registration_source skip_authorization updated user'.split()),
    'oauth2_provider.Grant': frozenset('application claims code code_challenge code_challenge_method created expires id nonce redirect_uri resource scope updated user'.split()),
    'oauth2_provider.AccessToken': frozenset('application created expires id id_token resource scope source_refresh_token token token_checksum updated user'.split()),
    'oauth2_provider.RefreshToken': frozenset('access_token application created id resource revoked token token_checksum token_family updated user'.split()),
    'oauth2_provider.IDToken': frozenset('application created expires id jti scope updated user'.split()),
    'oauth2_provider.DeviceGrant': frozenset('client_id device_code expires id interval last_checked scope status user user_code'.split()),
}

from .catalog_profiles import FIELD_NAMES as PROFILE_FIELD_NAMES, PROFILE_FIELDS, PROJECT_FIELDS
FIRST_PARTY_FIELD_NAMES.update(PROFILE_FIELD_NAMES)
FIRST_PARTY_FIELD_NAMES["makerspaces.MemberProfile"] |= frozenset(PROFILE_FIELDS.split())
FIRST_PARTY_FIELD_NAMES["makerspaces.MemberProject"] |= frozenset(PROJECT_FIELDS.split())

from .catalog_p2_presence import FIELD_NAMES as PRESENCE_FIELDS
FIRST_PARTY_FIELD_NAMES.update(PRESENCE_FIELDS)

UNMANAGED_FIELD_NAMES = {}

from .tenant_dump_modules import MODULE_FIELD_NAMES
FIRST_PARTY_FIELD_NAMES["makerspaces.Makerspace"] |= MODULE_FIELD_NAMES
FIRST_PARTY_FIELD_NAMES["makerspaces.Makerspace"] |= {"event_default_registration_audience"}
from .catalog_wp4 import field_snapshot
FIRST_PARTY_FIELD_NAMES = field_snapshot(FIRST_PARTY_FIELD_NAMES)
FIRST_PARTY_FIELD_NAMES["bookings.Booking"] |= {"cancelled_at", "status_before_cancel"}
from .catalog_notifications_contract import FIELD_NAMES as NOTIFICATION_FIELDS
FIRST_PARTY_FIELD_NAMES.update(NOTIFICATION_FIELDS)
from .catalog_p2_events import FIELD_NAMES as P2_EVENT_FIELDS
FIRST_PARTY_FIELD_NAMES.update(P2_EVENT_FIELDS)

# Mobile-only literal declarations extend the split T snapshot, never replace it.
FIRST_PARTY_FIELD_NAMES.update({
    'accounts.AccountPurgeObject': frozenset('attempts bucket deleted_at id last_error makerspace object_key quota_released_at size_bytes user'.split()),
    'accounts.AccountPurgeProgress': frozenset('done_at id makerspace user'.split()),
    'accounts.AccountRestoreIntent': frozenset('attestation_challenge client_platform consumed_at credential_fingerprint delivery expires_at id nonce_digest origin pending_secret provider redirect_uri token_digest user'.split()),
    'accounts.AppleRefreshCredential': frozenset('client_id id social_identity token_ciphertext updated_at version'.split()),
    'accounts.AppleRevocation': frozenset('attempts client_id created_at credential_id credential_version done_at id last_error next_attempt_at token_ciphertext user'.split()),
    'accounts.AttestationVerificationLog': frozenset('created_at id mode outcome platform'.split()),
    'accounts.DeviceActivityDay': frozenset('created_at grant id local_day makerspace platform'.split()),
    'accounts.PlatformAttestationSettings': frozenset('app_display_name id play_integrity_service_account updated_at'.split()),
    'integrations.EmailProviderEvent': frozenset('created_at event_id id makerspace reason'.split()),
    'integrations.MakerspaceMessagingSettings': frozenset('id makerspace sms_account_sid sms_auth_token sms_from_number sms_sender_key updated_at use_platform_sender whatsapp_access_token whatsapp_app_secret whatsapp_business_account_id whatsapp_phone_number_id whatsapp_sender_key whatsapp_webhook_verify_token'.split()),
    'integrations.MessagingConsent': frozenset('action channel configuration_generation created_at endpoint id lifted_suppression_id makerspace phone_e164 phone_verified_at sender_key source user'.split()),
    'integrations.MessagingDelivery': frozenset('accepted_at attempts audience billed_segments channel context created_at delivered_at error_code estimated_segments event event_key failed_at feature id lease_token lease_until makerspace max_attempts next_attempt_at progress_rank provider provider_message_id provider_source quota_reserved_at read_at recipient_alias_hash recipient_phone_hash scope segments sender_key sent_at skip_reason source_id source_type status template_name user'.split()),
    'integrations.MessagingRecipientAlias': frozenset('alias_hash channel first_seen_at id phone_hash sender_key'.split()),
    'integrations.MessagingRecipientCorrelation': frozenset('alias_known channel confirmed_at id phone_hash probe_delivery probe_notification_delivery probe_started_at sender_key state'.split()),
    'integrations.MessagingSenderCredential': frozenset('created_at id identity retired_at verify_token version webhook_secret wiped_at'.split()),
    'integrations.MessagingSenderIdentity': frozenset('active channel id makerspace owner retired_at sender_key tenant_reference'.split()),
    'integrations.MessagingSuppression': frozenset('channel created_at id lifted_at lifted_provider_at provider_at reason recipient_hash recipient_kind sender_key'.split()),
    'integrations.MessagingWebhookEvent': frozenset('attempts channel dedupe_id id kind makerspace next_attempt_at payload processed_at provider received_at sender_key state'.split()),
    'integrations.PlatformWhatsAppSettings': frozenset('access_token app_id app_secret business_account_id id is_enabled phone_number_id updated_at webhook_verify_token'.split()),
    'integrations.PushDeliveryAttempt': frozenset('attempts created_at delivery_log id last_error lease_token lease_until platform provider_source push_device recipient sent_at status'.split()),
    'integrations.SmsSendLog': frozenset('created_at id makerspace provider_source purpose status'.split()),
    'integrations.WhatsAppTemplateBinding': frozenset('audience business_account_id event feature id is_active language makerspace needs_review parameters template_name'.split()),
    'inventory.InventoryStockSnapshot': frozenset('available below_reorder id issued local_day makerspace out_of_stock product total'.split()),
    'machines.ConsumableCostRecord': frozenset('cost_total_minor currency id makerspace measurement_unit quantity recorded_at source_id source_kind unit_price_minor_per_measurement_unit'.split()),
    'machines.MachineStatusEvent': frozenset('at from_status id machine makerspace source to_status'.split()),
    'notifications.MemberPushDelivery': frozenset('attempts created_at envelope_delivery id inbox_row last_error lease_token lease_until platform provider_source push_device retryable sent_at status'.split()),
})

FIRST_PARTY_FIELD_NAMES['accounts.DeviceAttestationChallenge'] |= frozenset('signing_identities'.split())
FIRST_PARTY_FIELD_NAMES['accounts.DeviceGrant'] |= frozenset('attestation_key_id attestation_public_key authority'.split())
# L21b (#173): an event-role grant's one event snapshot (accounts/0055).
FIRST_PARTY_FIELD_NAMES['accounts.DeviceGrant'] |= frozenset({'event_id'})
FIRST_PARTY_FIELD_NAMES['accounts.NativeAppRegistration'] |= frozenset('min_supported_version signing_identities'.split())
FIRST_PARTY_FIELD_NAMES['accounts.PasswordResetEnvelope'] |= frozenset('purpose'.split())
FIRST_PARTY_FIELD_NAMES['accounts.PhoneVerificationChallenge'] |= frozenset('attestation_challenge credential_fingerprint'.split())
FIRST_PARTY_FIELD_NAMES['accounts.User'] |= frozenset('account_purged_at account_restored_at deletion_email_ciphertext deletion_purge_after deletion_requested_at deletion_username purge_started_at'.split())
FIRST_PARTY_FIELD_NAMES['integrations.EmailLog'] |= frozenset('bounced_at complained_at provider_message_id provider_source'.split())
FIRST_PARTY_FIELD_NAMES['integrations.PlatformSmsSettings'] |= frozenset('notifications_enabled notifications_from_number'.split())
FIRST_PARTY_FIELD_NAMES['inventory.InventoryProduct'] |= frozenset('cost_currency cost_unit unit_cost'.split())
FIRST_PARTY_FIELD_NAMES['machines.MachineConsumablePool'] |= frozenset('cost_currency cost_unit unit_cost'.split())
FIRST_PARTY_FIELD_NAMES['machines.MachineUsageEntry'] |= frozenset('member started_at'.split())
FIRST_PARTY_FIELD_NAMES['notifications.NotificationInboxRow'] |= frozenset('audience scope'.split())

# Orchestrator re-pins the live catalog after final schema/migration verification.
from .catalog_public_pages import FIELD_NAMES as PAGE_FIELD_NAMES
FIRST_PARTY_FIELD_NAMES.update(PAGE_FIELD_NAMES)

# Apply extensions last: older broadcast/website snapshots replace whole entries.
from .catalog_events_programme import FIELD_NAMES as PROGRAMME_FIELDS, EXTRA_FIELDS as PROGRAMME_EXTRA
FIRST_PARTY_FIELD_NAMES.update(PROGRAMME_FIELDS)
for _label, _names in PROGRAMME_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= frozenset(_names.split())
from .catalog_reimbursements_fields import FIELD_NAMES as REIMBURSEMENT_FIELDS
from .catalog_reimbursements import EXTRA_FIELDS as REIMBURSEMENT_EXTRA
FIRST_PARTY_FIELD_NAMES.update(REIMBURSEMENT_FIELDS)
for _label, _names in REIMBURSEMENT_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= frozenset(_names.split())
from .catalog_security import FIELD_NAMES as SECURITY_FIELDS
FIRST_PARTY_FIELD_NAMES.update(SECURITY_FIELDS)
from .catalog_r2_l2 import FIELD_NAMES as R2_L2_FIELDS, EXTRA_FIELDS as R2_L2_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L2_FIELDS)
for _label, _names in R2_L2_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_unified_accounts import FIELD_NAMES as UA1_FIELDS, EXTRA_FIELDS as UA1_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(UA1_FIELDS)
for _label, _names in UA1_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l4 import FIELD_NAMES as R2_L4_FIELDS, EXTRA_FIELDS as R2_L4_EXTRA
FIRST_PARTY_FIELD_NAMES.update(R2_L4_FIELDS)
for _label, _names in R2_L4_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= frozenset(_names.split())
from .catalog_login_security import FIELD_NAMES as S0_FIELDS, EXTRA_FIELDS as S0_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(S0_FIELDS)
for _label, _names in S0_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l10 import FIELD_NAMES as R2_L10_FIELDS  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L10_FIELDS)
from .catalog_r2_l11 import FIELD_NAMES as R2_L11_FIELDS, EXTRA_FIELDS as R2_L11_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L11_FIELDS)
for _label, _names in R2_L11_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l26 import EXTRA_FIELDS as R2_L26_EXTRA  # noqa: E402
for _label, _names in R2_L26_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_l3 import FIELD_NAMES as L3_FIELDS, EXTRA_FIELDS as L3_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(L3_FIELDS)
for _label, _names in L3_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l8 import FIELD_NAMES as R2_L8_FIELDS, EXTRA_FIELDS as R2_L8_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L8_FIELDS)
for _label, _names in R2_L8_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l6 import FIELD_NAMES as R2_L6_FIELDS, EXTRA_FIELDS as R2_L6_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L6_FIELDS)
for _label, _names in R2_L6_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l18 import FIELD_NAMES as R2_L18_FIELDS  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L18_FIELDS)
from .catalog_r2_l21a import FIELD_NAMES as R2_L21A_FIELDS, EXTRA_FIELDS as R2_L21A_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L21A_FIELDS)
for _label, _names in R2_L21A_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l22 import FIELD_NAMES as R2_L22_FIELDS, EXTRA_FIELDS as R2_L22_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L22_FIELDS)
for _label, _names in R2_L22_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_hackmoney_payments import FIELD_NAMES as HACKMONEY_FIELDS, EXTRA_FIELDS as HACKMONEY_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(HACKMONEY_FIELDS)
for _label, _names in HACKMONEY_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l25 import FIELD_NAMES as R2_L25_FIELDS  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_L25_FIELDS)
from .catalog_r2_submit_content import REIMBURSEMENT_EXTRA_FIELDS as R2_SUBMIT_CONTENT_EXTRA  # noqa: E402
for _label, _names in R2_SUBMIT_CONTENT_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_superadmin import FIELD_NAMES as R2_SUPERADMIN_FIELDS, EXTRA_FIELDS as R2_SUPERADMIN_EXTRA  # noqa: E402
FIRST_PARTY_FIELD_NAMES.update(R2_SUPERADMIN_FIELDS)
for _label, _names in R2_SUPERADMIN_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
from .catalog_r2_l9 import EXTRA_FIELDS as R2_L9_EXTRA  # noqa: E402
for _label, _names in R2_L9_EXTRA.items():
    FIRST_PARTY_FIELD_NAMES[_label] |= _names
