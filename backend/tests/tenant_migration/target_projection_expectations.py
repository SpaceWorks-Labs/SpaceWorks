"""Independent target projection values, including the intended merged opt-ins.

Callables explicitly pin generated credentials and the current revocation time;
all static values are literals rather than being copied from production registries.
"""

import secrets

from django.utils import timezone

from apps.makerspaces.loan_context_generations import new_generations
from apps.makerspaces.models import Makerspace, MakerspaceMembership


EXPECTED_TARGET_VALUES = {
    ("events.Event", "organization_admission_blocked"): True,
    ("events.EventSeries", "organization_admission_blocked"): True,
    ("operations.SavedView", "shared"): False,
    ("operations.SavedView", "state"): {},
    ("makerspaces.MakerspaceMembershipSettings", "join_mode"): "approval",
    ("makerspaces.MakerspaceMembershipSettings", "vouch_replaces_approval"): False,
    ("makerspaces.MembershipRequest", "state"): "canceled",
    ("makerspaces.MembershipRequest", "admission_managed"): False,
    ("payments.MakerspaceBillingSettings", "reminder_days_before"): [],
    ("payments.MakerspaceBillingSettings", "reminder_days_after"): [],
    ("payments.MakerspaceBillingSettings", "max_reminders"): 0,
    ("makerspaces.Makerspace", "frontend_domain"): None,
    ("makerspaces.Makerspace", "frontend_domain_status"): Makerspace.DomainStatus.PENDING,
    ("makerspaces.Makerspace", "domain_verified_at"): None,
    ("makerspaces.Makerspace", "frontend_domain_changed_at"): None,
    ("makerspaces.Makerspace", "hidden_from_central_directory"): False,
    ("makerspaces.Makerspace", "archived_at"): None,
    ("makerspaces.Makerspace", "resource_limit_overrides"): {},
    ("makerspaces.Makerspace", "storage_bytes_used"): 0,
    ("makerspaces.Makerspace", "membership_policy"): Makerspace.MembershipPolicy.REQUEST,
    ("makerspaces.Makerspace", "referrals_enabled"): False,
    ("makerspaces.Makerspace", "telegram_group_chat_id"): "",
    ("makerspaces.Makerspace", "smtp_host"): "",
    ("makerspaces.Makerspace", "smtp_port"): 587,
    ("makerspaces.Makerspace", "smtp_username"): "",
    ("makerspaces.Makerspace", "smtp_use_tls"): True,
    ("makerspaces.Makerspace", "smtp_use_ssl"): False,
    ("makerspaces.Makerspace", "enabled_modules"): [
        "public_inventory", "request_workflow", "staff_admin", "scanner",
        "evidence_uploads", "qr_management", "member_accounts",
    ],
    ("makerspaces.Makerspace", "enabled_features"): [
        "reports.saved_views", "billing.documents", "staff.invitations",
        "ui.delight", "ui.easter_eggs",
        "charges.enabled", "charges.bookings", "charges.events", "charges.machines",
        "charges.membership", "charges.loans", "inventory.self_checkout",
        "payments.enabled", "mobile.push", "presence.geofence", "loans.enabled",
        "events.anonymous_feedback", "billing.disputes", "billing.capture_flags", "finance.ledger",
        "charges.pricing", "loans.fee_waivers", "machines.job_requests", "machines.job_quotes",
        "mobile.watch_actions",
        # Release 2 default-on capabilities (donations, calendar feeds, gallery search, shop,
        # help centre, inventory and room maintenance reminders).
        "charges.donations", "bookings.calendar_feed", "events.calendar_feed", "events.gallery_search",
        "shop.holds", "shop.public_stock", "shop.receipts", "charges.shop", "platform.help_centre",
        "inventory.maintenance_reminders", "bookings.room_maintenance_reminders",
        # Default-on events, email and legal capabilities added since.
        "events.team_moderation", "events.crew_kinds", "events.badge_designer", "events.badge_desk_print",
        "events.role_badges", "events.discovery_filters", "events.space_insights", "email.sender_identity",
        "legal.space_pages",
    ],
    ("events.EventRegistration", "pay_by"): None,
    ("events.HackathonTeam", "deleted_at"): None,
    ("events.HackathonTeam", "deleted_snapshot"): {},
    ("inventory.EquipmentKitTemplate", "published_for_contexts"): False,
    ("machines.ServiceRequestConsumableUsage", "device_ref"): "",
    ("makerspaces.Makerspace", "loan_context_generations"): new_generations,
    ("makerspaces.MakerspaceMembership", "receives_notifications"): True,
    ("makerspaces.MakerspaceMembership", "role"): MakerspaceMembership.Role.CUSTOM,
    ("makerspaces.MakerspaceMembership", "can_refer"): True,
    ("makerspaces.MakerspaceMembership", "can_verify"): False,
    ("makerspaces.MembershipRequest", "auto_activate_on_claim"): False,
    ("makerspaces.Station", "created_by"): None,
    ("machines.MachineType", "managing_action"): "",
    ("integrations.NotificationDestination", "is_active"): False,
    ("evidence.EvidenceRetentionPolicy", "abandoned_upload_cleanup_enabled"): False,
    ("evidence.EvidenceRetentionPolicy", "abandoned_upload_retention_days"): None,
    ("evidence.EvidencePhoto", "consumption_state"): "legacy_unknown",
    # Phase 7a: an imported device carries no live authority until the target re-enrolls it.
    ("devices.Device", "status"): "pending",
    ("devices.Device", "last_seen_at"): None,
    ("devices.Device", "offline_since"): None,
    ("devices.Device", "offline_notified_at"): None,
    ("devices.Device", "revoked_at"): None,
    ("devices.Device", "revoked_by"): None,
    # Phase 7b: imported printer delivery is inert until re-created on the target.
    ("devices.DeviceCommand", "status"): "cancelled",
    ("devices.DeviceCommand", "lease_token_digest"): None,
    ("devices.DeviceCommand", "lease_expires_at"): None,
    ("devices.PrinterDeviceBinding", "enabled"): False,
    ("devices.PrinterDeviceBinding", "auto_apply_terminal"): False,
    ("devices.PrinterJob", "state"): "needs_review",
    # Phase 7c: acknowledged delivery ownership cannot travel.
    ("devices.DeviceCommand", "acknowledged_at"): None,
    # Target operators re-enable renewal, scheduled work and optional disclosures.
    ("makerspaces.MembershipPlan", "auto_renew"): False,
    ("makerspaces.MembershipPlan", "reminder_days_before"): [],
    ("makerspaces.MembershipPlan", "reminder_days_after"): [],
    ("makerspaces.MembershipTerm", "renewal_attempts"): 0,
    ("makerspaces.MembershipTerm", "renewal_retry_at"): None,
    ("bookings.Booking", "calendar_sequence"): 0,
    ("machines.Machine", "public_fields"): [],
    ("operations.StocktakePolicy", "variance_threshold"): None,
    ("operations.StocktakeSession", "variance_threshold"): None,
    ("operations.StocktakeSession", "approval_required"): True,
    ("operations.StocktakeSchedule", "is_active"): False,
    # Source-keyed codes are replaced and revoked at the actual target import time.
    ("events.EventInvite", "code_digest"): secrets.token_hex,
    ("events.EventInvite", "email_digest"): "",
    ("events.EventInvite", "revoked_at"): timezone.now,
    ("events.EventPromoCode", "code_digest"): secrets.token_hex,
    ("events.EventPromoCode", "revoked_at"): timezone.now,
}

# BK-D booking communication history cannot resume target sends.
EXPECTED_TARGET_VALUES.update({
    ("bookings.BookingBroadcast", "status"): "cancelled",
    ("bookings.BookingBroadcast", "recipient_cursor"): 0,
    ("bookings.BookingBroadcast", "recipients_complete"): True,
    ("bookings.BookingBroadcastDelivery", "outbox"): None,
    ("bookings.BookingBroadcastDelivery", "status"): "skipped",
})

# The integrated event history uses the same inert communication projection.
EXPECTED_TARGET_VALUES.update({
    ("events.EventBroadcast", "status"): "cancelled",
    ("events.EventBroadcast", "recipient_cursor"): 0,
    ("events.EventBroadcast", "recipients_complete"): True,
    ("events.EventBroadcastDelivery", "outbox"): None,
    ("events.EventBroadcastDelivery", "status"): "skipped",
})

# Websites stay unreleased and unframed until target staff act; artwork versions re-pin.
EXPECTED_TARGET_VALUES.update({
    ("bookings.BookingResourcePage", "released"): False,
    ("events.EventPage", "released"): False,
    ("events.EventCertificateArtwork", "version_id"): "",
    ("makerspaces.Makerspace", "website_embed_origins"): [],
})

# Public profile disclosure needs fresh target-side consent and publication.
EXPECTED_TARGET_VALUES.update({
    ("makerspaces.MemberProfile", "public_consented_at"): None,
    **{("makerspaces.MemberProfile", name): False for name in (
        "public_visible", "show_activity_graph", "show_bookings", "show_events", "show_loans",
        "show_machine_activity", "show_projects", "show_speaking",
    )},
    ("makerspaces.MemberProject", "public_visible"): False,
})

# Events programme: imported programme rows carry history, never operational authority.
EXPECTED_TARGET_VALUES.update({
    ("events.EventRoleAssignment", "host_waiver"): None,
    ("events.EventRoleAssignment", "host_waiver_version_accepted"): "",
    ("events.EventRoleAssignment", "host_waiver_accepted_at"): None,
    ("events.EventRoleAssignment", "imported_inert"): True,
    ("events.HackathonConfig", "enabled"): False,
    ("events.HackathonConfig", "finder_enabled"): False,
    ("events.HackathonConfig", "gallery_publication"): None,
    ("events.HackathonConfig", "results_revision"): None,
    ("events.HackathonConfig", "application_opens_at"): None,
    ("events.HackathonConfig", "application_closes_at"): None,
    ("events.HackathonConfig", "submission_opens_at"): None,
    ("events.HackathonConfig", "submission_deadline"): None,
    ("events.HackathonTeam", "seeking_members"): False,
    ("events.HackathonTeam", "public_profile_refs"): [],
    ("events.HackathonTeam", "roster_reopened_until"): None,
    ("events.HackathonFinderProfile", "opted_in"): False,
    ("events.ApplicationDecision", "active_draft"): False,
    ("events.ApplicationDecisionBatch", "state"): "cancelled",
    ("events.HackathonApplication", "optional_consents"): {},
    ("events.EventHelpRequest", "state"): "expired",
    ("events.EventHelpRequest", "claimed_by"): None,
    ("events.EventHelpRequest", "claim_uuid"): None,
    ("events.EventHelpRequest", "claim_expires_at"): None,
    ("events.EventMemberPresentation", "print_photo_consent"): False,
    ("events.EventMemberPresentation", "public_card_consent"): False,
    ("events.EventMemberPresentation", "public_card_scopes"): [],
    ("events.EventMemberPresentation", "selected_profile"): None,
    ("events.EventMemberPresentation", "selected_membership"): None,
    ("events.EventCertificatePublicationPolicy", "enabled"): False,
    ("events.EventAttendanceCertificate", "public_verification_enabled"): False,
    ("events.EventAttendanceCertificate", "holder_name_public"): False,  # idcards-best certificates
    ("events.EventRegistration", "credential_mode"): "inert",
    ("events.ResultPublicationState", "current_announcement"): None,
    ("events.GalleryPublication", "active"): False,
    ("events.GalleryConsent", "metadata_public"): False,
    ("events.GalleryConsentItem", "active"): False,
    ("events.ParticipantSponsorResumeConsent", "state"): "revoked",
    ("events.ParticipantSponsorResumeConsent", "revoked_at"): timezone.now,
    ("events.HackathonSubmission", "public_requested"): False,
    ("events.HackathonSubmission", "public_asset_ids"): [],
    ("events.SubmissionLink", "public_requested"): False,
    ("events.SnapshotAsset", "public_requested"): False,
    ("events.SnapshotLink", "public_requested"): False,
    ("events.EventAward", "public_requested"): False,
    ("events.EventAssetUsage", "budget_bytes"): 0,
    ("events.EventAssetUsage", "reserved_bytes"): 0,
    ("events.EventAssetUsage", "failed_cleanup_bytes"): 0,
    ("events.EventCertificateLibraryArtwork", "version_id"): "",
    ("events.EventBroadcast", "confirmed_preview"): None,
    ("events.EventBroadcast", "available_at"): None,
    ("events.EventRolePosting", "state"): "closed",
    ("events.EventShift", "state"): "closed",
    ("events.MentorRound", "state"): "closed",
    ("events.JudgingRound", "state"): "closed",
    ("events.MentorTeamAssignment", "state"): "ended",
    ("events.MentorTeamAssignment", "ended_at"): timezone.now,
    ("events.JudgeAssignment", "state"): "invalidated",
    **{(label, name): "" for label in ("events.SubmissionAsset", "events.HackathonParticipantAsset")
       for name in ("source_version_id", "verification_version_id", "source_etag", "multipart_upload_id")},
    **{(label, "upload_not_after"): None for label in ("events.SubmissionAsset", "events.HackathonParticipantAsset")},
    **{(label, "reserved_bytes"): 0 for label in ("events.SubmissionAsset", "events.HackathonParticipantAsset")},
})

# Event reimbursements and staged forms: imported programmes and assignments arrive paused
# with no live window; source upload leases and bucket versions never travel.
EXPECTED_TARGET_VALUES.update({
    ("event_reimbursements.ReimbursementProgramme", "enabled"): False,
    ("event_reimbursements.ReimbursementProgramme", "imported_paused"): True,
    ("event_reimbursements.ReimbursementProgramme", "request_opens_at"): None,
    ("event_reimbursements.ReimbursementProgramme", "request_closes_at"): timezone.now,
    ("events.StageFormAssignment", "creation_operation_id"): None,
    ("events.StageFormAssignment", "imported_paused"): True,
    **{(label, name): value for label in ("events.StageFormAsset", "payments.FinanceAttachment")
       for name, value in (("lease_token", None), ("lease_until", None), ("attempts", 0),
                           ("staging_version_id", ""), ("final_version_id", ""))},
})

# Staging integration (2026-10-19..23): mobile accounts and messaging, cloud email
# providers and the Pages publication pointers.
EXPECTED_TARGET_VALUES.update({
    ('accounts.User', 'account_restored_at'): None,  # Target issues its own revocable sessions.
    ('accounts.User', 'deletion_email_ciphertext'): '',  # Source platform-encrypted erasure address never travels.
    ('accounts.User', 'deletion_username'): '',  # Target chooses its own random erasure pseudonym.
    ('events.EventPage', 'published_revision'): None,  # Fresh target release required.
    ('integrations.MessagingConsent', 'action'): 'opted_out',  # Target members and operators must re-establish addressed sending authority.
    ('integrations.MessagingConsent', 'configuration_generation'): 0,  # Target members and operators must re-establish addressed sending authority.
    ('integrations.MessagingConsent', 'endpoint'): None,  # Target members and operators must re-establish addressed sending authority.
    ('integrations.MessagingConsent', 'lifted_suppression_id'): [],  # Target members and operators must re-establish addressed sending authority.
    ('integrations.MessagingConsent', 'sender_key'): '',  # Target members and operators must re-establish addressed sending authority.
    ('integrations.WhatsAppTemplateBinding', 'is_active'): False,  # Target members and operators must re-establish addressed sending authority.
    ('integrations.WhatsAppTemplateBinding', 'needs_review'): True,  # Target members and operators must re-establish addressed sending authority.
    ('makerspaces.Makerspace', 'email_provider'): 'inherit',  # Target operator configures mail transport.
    ('makerspaces.Makerspace', 'email_provider_config'): '',  # Source encrypted transport secrets never travel.
    ('makerspaces.MakerspacePublicPage', 'published_revision'): None,  # Fresh target publication required.
})

# Release-1 programmes: account erasure material is target-chosen, composed pages need a
# fresh target publication, addressed messaging travels inert, and the target operator
# configures its own mail transport.
EXPECTED_TARGET_VALUES.update({
    ("accounts.User", "account_restored_at"): None,
    ("accounts.User", "deletion_email_ciphertext"): "",
    ("accounts.User", "deletion_username"): "",
    ("events.EventPage", "published_revision"): None,
    ("makerspaces.MakerspacePublicPage", "published_revision"): None,
    ("integrations.MessagingConsent", "action"): "opted_out",
    ("integrations.MessagingConsent", "configuration_generation"): 0,
    ("integrations.MessagingConsent", "endpoint"): None,
    ("integrations.MessagingConsent", "lifted_suppression_id"): [],
    ("integrations.MessagingConsent", "sender_key"): "",
    ("integrations.WhatsAppTemplateBinding", "is_active"): False,
    ("integrations.WhatsAppTemplateBinding", "needs_review"): True,
    ("makerspaces.Makerspace", "email_provider"): "inherit",
    ("makerspaces.Makerspace", "email_provider_config"): "",
})

# Release 2 L1/L2: the online join link and the event embed policy are target-established.
EXPECTED_TARGET_VALUES.update({
    ("events.Event", "join_url_encrypted"): "",
    ("events.EventEmbedPolicy", "allowed_origins"): [],
    ("events.EventEmbedPolicy", "enabled"): False,
})
