"""Target-side reconstruction rules for fields omitted from PORTABLE archives."""

from enum import StrEnum


class OmittedFieldDisposition(StrEnum):
    """Closed importer contract for a source field that has no archived value.

    FRESH means generate through the field's callable, retry collisions, and verify
    uniqueness again immediately before commit. DERIVED values come from target-owned
    state; DROP_ROW and QUARANTINE never insert the source row as an actionable row.
    """

    DROP_ROW = "drop_row"
    FRESH = "fresh"
    EMPTY_STRING = "empty_string"
    NULL = "null"
    DERIVED = "derived"
    QUARANTINE = "quarantine"


DROP_ROW = OmittedFieldDisposition.DROP_ROW
FRESH = OmittedFieldDisposition.FRESH
EMPTY_STRING = OmittedFieldDisposition.EMPTY_STRING
NULL = OmittedFieldDisposition.NULL
DERIVED = OmittedFieldDisposition.DERIVED
QUARANTINE = OmittedFieldDisposition.QUARANTINE


def _rules(disposition, *fields):
    return {field: disposition for field in fields}


OMITTED_FIELD_RECONSTRUCTIONS = {
    ("makerspaces.Makerspace", "email_provider"): EMPTY_STRING,
    ("makerspaces.Makerspace", "email_provider_config"): EMPTY_STRING,
    ("events.EventMemberCard", "public_id"): FRESH,
    ("events.EventBroadcast", "confirmed_preview"): NULL,
    ("events.EventFormRevision", "created_by"): NULL,
    ("events.EventAttendanceCertificate", "render_token"): NULL,
    ("events.EventMemberPresentation", "selected_profile"): NULL,
    ("events.EventMemberPresentation", "selected_membership"): NULL,
    **{(label, name): disposition for label in (
        "events.SubmissionAsset", "events.HackathonParticipantAsset",
    ) for name, disposition in (
        ("staging_key", DERIVED), ("verification_key", DERIVED), ("claim", DERIVED),
        ("source_version_id", EMPTY_STRING), ("verification_version_id", EMPTY_STRING),
        ("source_etag", EMPTY_STRING), ("multipart_upload_id", EMPTY_STRING), ("upload_not_after", NULL),
    )},
    ("bookings.BookingBroadcastDelivery", "outbox"): NULL,
    ("events.EventBroadcastDelivery", "outbox"): NULL,
    # Imported consent is inert (catalog_messaging): the sender/proof binding is
    # deployment-local, so the target projects an unbound, empty consent row.
    ("integrations.MessagingConsent", "sender_key"): EMPTY_STRING,
    ("integrations.MessagingConsent", "endpoint"): NULL,
    ("integrations.MessagingConsent", "configuration_generation"): DERIVED,
    ("integrations.MessagingConsent", "lifted_suppression_id"): DERIVED,
    **_rules(
        DROP_ROW,
        ("apiclients.ApiClient", "client_id"),
        ("apiclients.ApiClient", "secret_encrypted"),
        ("apiclients.ApiClient", "import_provenance_digest"),
        ("apiclients.ApiClient", "credential_delivered_at"),
        # The retained rotation-grace secret goes with the current one: a client the
        # target cannot authenticate is a client the target must re-issue.
        ("apiclients.ApiClient", "previous_secret_encrypted"),
        # Webhook destinations cannot satisfy their credential check constraint after
        # the encrypted webhook is removed, even when the source row is inactive.
        ("integrations.NotificationDestination", "webhook_url"),
        ("integrations.NotificationDestination", "signing_secret"),
        ("integrations.NotificationDestination", "previous_signing_secret"),
    ),
    **_rules(
        FRESH,
        ("bookings.BookableSpace", "public_token"),
        ("bookings.Booking", "public_token"),
        ("bookings.Booking", "checkin_token"),
        ("events.Event", "public_token"),
        ("events.EventSeries", "public_token"),
        # Deliberately invalidate source event check-in QR codes at the trust boundary.
        ("events.EventRegistration", "checkin_token"),
        ("hardware_requests.HardwareRequest", "public_token"),
        ("machines.MachineServiceRequest", "public_token"),
        ("makerspaces.Makerspace", "public_api_key"),
    ),
    **_rules(
        DERIVED,
        ("events.EventInvite", "code_digest"),
        ("events.EventInvite", "email_digest"),
        ("events.EventPromoCode", "code_digest"),
        ("events.EventRegistration", "email_exact_hash"),
        ("events.EventRegistration", "email_hash_generation"),
        # Unlike public_api_key, this callable-generated field has no database
        # uniqueness contract, so it cannot use the collision-checked FRESH rule.
        ("makerspaces.Makerspace", "domain_verification_token"),
        # The importer owns this outright: the row is created IMPORTING and only the
        # activation transition may make it ACTIVE, so no archived value may travel.
        ("makerspaces.Makerspace", "lifecycle_state"),
        # semantic_remap rewrites actor/target/meta on import, so a source MAC
        # cannot survive: the target recomputes it under the TARGET key after all
        # remapping. Never carry the source value.
        ("audit.AuditLog", "row_mac"),
        # Full-text vectors are recomputed by the search trigger on the first write the
        # importer makes; carrying a source value would only be overwritten.
        ("inventory.InventoryProduct", "search_vector"),
        ("machines.Machine", "search_vector"),
        ("events.Event", "search_vector"),
    ),
    **_rules(
        EMPTY_STRING,
        ("machines.Machine", "camera_feed_url"),
        ("makerspaces.Makerspace", "telegram_bot_token"),
        ("makerspaces.Makerspace", "smtp_password"),
        ("makerspaces.Makerspace", "slack_webhook_url"),
        ("events.Event", "join_url_encrypted"),
        ("makerspaces.Makerspace", "mattermost_webhook_url"),
        ("makerspaces.Makerspace", "discord_webhook_url"),
        ("payments.MakerspacePaymentSettings", "stripe_publishable_key"),
        ("payments.MakerspacePaymentSettings", "stripe_secret_key"),
        ("payments.MakerspacePaymentSettings", "stripe_webhook_secret"),
        ("payments.MakerspacePaymentSettings", "razorpay_key_id"),
        ("payments.MakerspacePaymentSettings", "razorpay_key_secret"),
        ("payments.MakerspacePaymentSettings", "razorpay_webhook_secret"),
        ("payments.Payment", "checkout_url"),
        ("payments.Payment", "stripe_checkout_url"),
    ),
    **_rules(
        NULL,
        # A device key is proven per deployment; the imported device arrives pending
        # and re-enrolls (target_projection_devices), so no key travels.
        ("devices.Device", "public_key"),
        ("devices.Device", "key_fingerprint"),
        ("devices.DeviceCommand", "lease_token_digest"),
        ("makerspaces.Station", "created_by"),
        # Projection provenance only: the target rebuilds the link from the canonical
        # series collaboration, and a carried-over id would point at a source row.
        ("events.EventCollaborator", "source_series_collaboration"),
        # A transient object-expiry claim credential. Nullable, and the sweep reissues
        # one when it next claims the row; carrying it would hand the target a live
        # claim it never issued.
        ("evidence.EvidenceObjectRetentionState", "claim_token"),
        # Nullable AND globally unique, so the guard requires NULL: a freshly
        # generated identity would claim provenance the target has not attested. The
        # target reseals its own rows (row_mac is DERIVED above).
        ("audit.AuditLog", "event_uuid"),
        ("machines.Machine", "legacy_print_printer_id"),
        ("machines.MachineConsumableAdjustment", "legacy_filament_adjustment_id"),
        ("machines.MachineConsumablePool", "legacy_filament_spool_id"),
        ("machines.MachineServiceRequest", "legacy_print_request_id"),
        ("machines.MachineUsageEntry", "legacy_manual_print_log_id"),
        ("machines.ServiceQueue", "legacy_print_bucket_id"),
        ("machines.ServiceRequestFile", "legacy_print_request_file_id"),
        ("payments.MakerspacePaymentSettings", "connect_account_id"),
        ("payments.Payment", "external_order_id"),
        ("payments.Payment", "external_payment_id"),
        # Same rule as the payment's own external ids: a provider-side refund id names a
        # movement of money at a vendor account the target does not hold, and its unique
        # constraint is what `unique_values` already calls inert once the value is dropped.
        ("payments.Refund", "external_refund_id"),
        ("payments.Payment", "stripe_connected_account_id"),
        ("payments.Payment", "stripe_checkout_session_id"),
        ("payments.Payment", "stripe_checkout_session_expired_at"),
        ("payments.Payment", "stripe_payment_intent_id"),
    ),
}

# Release 2 L6: claim and transfer token digests are bearer material. The target mints
# fresh unclaimable values; the buyer or sender re-sends the invite.
OMITTED_FIELD_RECONSTRUCTIONS.update(_rules(
    FRESH, ("events.EventOrderSeat", "claim_token_digest"), ("events.EventTicketTransfer", "token_digest")))

# Release 2 L18: a guest's donation and pledge link secrets are bearer material; the target
# mints fresh values (guests get fresh links).
OMITTED_FIELD_RECONSTRUCTIONS.update(_rules(
    FRESH, ("payments.Donation", "access_secret"), ("payments.DonationPledge", "manage_secret")))
# Release 2 L22: a guest's status-link secret is bearer material; the target mints a fresh one.
OMITTED_FIELD_RECONSTRUCTIONS.update(_rules(FRESH, ("shop.ShopOrder", "status_secret")))
# Release 2 L16: a technician's opt-in link digest and bot-proven chat id are not carried; the
# target stores them empty and the technician opts in again there.
OMITTED_FIELD_RECONSTRUCTIONS.update(_rules(
    EMPTY_STRING, ("maintenance.TechnicianContact", "opt_in_digest"),
    ("maintenance.TechnicianContact", "telegram_chat_id")))
# Loan-context concurrency epochs are deployment-local; the target derives fresh ones
# from the field default (never the source's epochs).
OMITTED_FIELD_RECONSTRUCTIONS.update(_rules(DERIVED, ("makerspaces.Makerspace", "loan_context_generations")))
