"""Literal programme §3a dispositions: imported programme authority is reset; the new
certificate media-grant columns are dropped. A static list: never derived at test time."""

from apps.tenant_migration.tenant_dump_types import AuthorityDisposition as D


def _fields(label, names, dispositions):
    return [((label, name), (dispositions,)) for name in names.split()]


PROGRAMME_EXPECTED = dict([
    *_fields("events.EventRoleAssignment", "host_waiver host_waiver_version_accepted host_waiver_accepted_at imported_inert", D.RESET),
    *_fields("events.HackathonConfig", "enabled finder_enabled gallery_publication results_revision application_opens_at application_closes_at submission_opens_at submission_deadline", D.RESET),
    *_fields("events.HackathonTeam", "seeking_members public_profile_refs roster_reopened_until", D.RESET),
    *_fields("events.HackathonFinderProfile", "opted_in", D.RESET),
    *_fields("events.ApplicationDecision", "active_draft", D.RESET),
    *_fields("events.HackathonApplication", "optional_consents", D.RESET),
    *_fields("events.EventHelpRequest", "state claimed_by claim_uuid claim_expires_at", D.RESET),
    *_fields("events.EventMemberPresentation", "print_photo_consent public_card_consent public_card_scopes selected_profile selected_membership", D.RESET),
    *_fields("events.EventCertificatePublicationPolicy", "enabled", D.RESET),
    *_fields("events.EventAttendanceCertificate", "public_verification_enabled holder_name_public", D.RESET),
    *_fields("events.EventRegistration", "credential_mode", D.RESET),
    *_fields("events.ResultPublicationState", "current_announcement", D.RESET),
    *_fields("events.GalleryPublication", "active", D.RESET),
    *_fields("events.GalleryConsent", "metadata_public", D.RESET),
    *_fields("events.GalleryConsentItem", "active", D.RESET),
    *_fields("events.ParticipantSponsorResumeConsent", "state revoked_at", D.RESET),
    *_fields("events.HackathonSubmission", "public_requested public_asset_ids", D.RESET),
    *_fields("events.SubmissionLink", "public_requested", D.RESET),
    *_fields("events.SnapshotAsset", "public_requested", D.RESET),
    *_fields("events.SnapshotLink", "public_requested", D.RESET),
    *_fields("events.EventAward", "public_requested", D.RESET),
    *_fields("events.EventAssetUsage", "budget_bytes reserved_bytes failed_cleanup_bytes", D.RESET),
    *_fields("events.EventCertificateLibraryArtwork", "version_id", D.RESET),
    *_fields("events.EventBroadcast", "confirmed_preview available_at", D.RESET),
    *_fields("events.EventRolePosting", "state", D.RESET),
    *_fields("events.EventShift", "state", D.RESET),
    *_fields("events.MentorRound", "state", D.RESET),
    *_fields("events.JudgingRound", "state", D.RESET),
    *_fields("events.MentorTeamAssignment", "state ended_at", D.RESET),
    *_fields("events.JudgeAssignment", "state", D.RESET),
    *_fields("events.SubmissionAsset", "source_version_id verification_version_id source_etag multipart_upload_id upload_not_after reserved_bytes", D.RESET),
    *_fields("events.HackathonParticipantAsset", "source_version_id verification_version_id source_etag multipart_upload_id upload_not_after reserved_bytes", D.RESET),
    *_fields("events.ApplicationDecisionBatch", "state", D.RESET),
    *_fields("integrations.NotificationMediaGrant", "certificate storage_makerspace source_revision recipient_id_snapshot integration_generation integration_identity", D.DROP),
])
