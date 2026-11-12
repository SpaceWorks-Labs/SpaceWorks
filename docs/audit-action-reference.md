# Audit action reference

The English labels below come from the audit presentation catalogue and reviewed action keys.
The platform and makerspace audit screens apply the same metadata policy.
Entries with withheld metadata show the action label and omit the stored metadata.

The table lists 1,429 actions: 1,390 presentation-catalogue entries, 20 reviewed wrapper actions that
show a label built from the key, and 19 dynamic actions under the deny policy. A further 60 shared-service
prefixes are listed at the end. The sources are `backend/apps/audit/presentation_catalog.py`,
`presentation_fallback_labels.py` and `presentation_catalog_dynamic.py`.

| Action key | English label | Metadata displayed |
| --- | --- | --- |
| `access_token.created` | Personal access token created | Reviewed fields only |
| `access_token.revoked` | Personal access token revoked | None declared |
| `account.apple_credential_stored` | Apple revocation credential stored | None declared |
| `account.apple_revocation_retry` | Apple revocation deferred | Reviewed fields only |
| `account.apple_revocation_unavailable` | Apple revocation unavailable | Reviewed fields only |
| `account.apple_revoked` | Apple authorization revoked | None declared |
| `account.converted` | Staff account converted to a personal account | Reviewed fields only |
| `account.credentials_revoked` | Account credentials revoked | Reviewed fields only |
| `account.deletion_refused` | Account deletion refused | Reviewed fields only |
| `account.deletion_requested` | Account deletion requested | Reviewed fields only |
| `account.disabled` | Account disabled by the platform administrator | None declared |
| `account.enabled` | Account re-enabled by the platform administrator | None declared |
| `account.locale_changed` | Account language changed | Reviewed fields only |
| `account.merge_cancelled` | Account link cancelled | Reviewed fields only |
| `account.merge_codes_resent` | Account link codes resent | Reviewed fields only |
| `account.merge_proof_failed` | Account link proof rejected | Reviewed fields only |
| `account.merge_started` | Account link started | Reviewed fields only |
| `account.merged` | Accounts linked into one | Reviewed fields only |
| `account.obligation_after_deletion` | Charge recorded after account deletion | Reviewed fields only |
| `account.profile_updated` | Account profile updated | Reviewed fields only |
| `account.purge_object_deleted` | Account image bytes deleted | None declared |
| `account.purge_object_quota_released` | Account image quota released | None declared |
| `account.purge_object_retry` | Account image cleanup deferred | Reviewed fields only |
| `account.purge_started` | Account identity purge started | None declared |
| `account.purged` | Account identity purged | Reviewed fields only |
| `account.restored` | Account restored | Reviewed fields only |
| `account.saved_detail_deleted` | Account saved detail deleted | None declared |
| `account.saved_detail_intent_completed` | Account saved detail intent completed | None declared |
| `account.saved_detail_intent_created` | Account saved detail intent created | None declared |
| `account.saved_detail_intent_expired` | Account saved detail intent expired | None declared |
| `account.saved_detail_intent_retry_required` | Account saved detail intent retry required | None declared |
| `account.saved_detail_updated` | Account saved detail updated | None declared |
| `account.saved_details_erased` | Account saved details erased | None declared |
| `account.saved_details_export_completed` | Account saved details export completed | None declared |
| `account.saved_details_export_expired` | Account saved details export expired | None declared |
| `account.saved_details_export_requested` | Account saved details export requested | None declared |
| `account.saved_details_export_started` | Account saved details export started | None declared |
| `account.saved_resume_cleanup_completed` | Account saved resume cleanup completed | None declared |
| `account.saved_resume_created` | Account saved resume created | None declared |
| `account.saved_resume_deleted` | Account saved resume deleted | None declared |
| `account.saved_resume_retired` | Account saved resume retired | None declared |
| `account.saved_resume_validation_claimed` | Account saved resume validation claimed | None declared |
| `account.saved_resume_validation_completed` | Account saved resume validation completed | None declared |
| `account.saved_resume_validation_requested` | Account saved resume validation requested | None declared |
| `account.session_revoked` | Account session revoked | Reviewed fields only |
| `account.tenant_identity_scrubbed` | Tenant account identity scrubbed | None declared |
| `account.tenant_purged` | Tenant account purge completed | None declared |
| `account_pii.key_created` | Account pii key created | None declared |
| `account_pii.key_preparation_claimed` | Account pii key preparation claimed | None declared |
| `account_pii.key_preparation_failed` | Account pii key preparation failed | None declared |
| `account_pii.key_rotated` | Account pii key rotated | None declared |
| `account_pii.keys_erased` | Account pii keys erased | Withheld |
| `account_pii.keys_revoked` | Account pii keys revoked | Withheld |
| `account_pii.rotation_claimed` | Account pii rotation claimed | None declared |
| `analytics.connection_updated` | Analytics connection changed | Reviewed fields only |
| `analytics.credentials_viewed` | Analytics credentials viewed | Reviewed fields only |
| `analytics.dashboard_viewed` | Analytics dashboard opened | Reviewed fields only |
| `analytics.grafana_bundle_downloaded` | Grafana bundle downloaded | Reviewed fields only |
| `analytics.grafana_connection_tested` | Grafana connection tested | Reviewed fields only |
| `analytics.grafana_connection_updated` | Grafana connection changed | Reviewed fields only |
| `analytics.grafana_credentials_viewed` | Grafana connection viewed | Reviewed fields only |
| `analytics.grafana_dashboard_viewed` | Grafana dashboard opened | Reviewed fields only |
| `analytics.grafana_token_created` | Grafana token saved | Reviewed fields only |
| `analytics.grafana_token_revoked` | Grafana token removed | Reviewed fields only |
| `analytics.grafana_token_rotated` | Grafana token replaced | Reviewed fields only |
| `analytics.login_created` | Analytics database login created | Reviewed fields only |
| `analytics.login_revoked` | Analytics database login revoked | Reviewed fields only |
| `analytics.login_rotated` | Analytics database login password rotated | Reviewed fields only |
| `analytics.telemetry_updated` | Web telemetry settings changed | Reviewed fields only |
| `api_client.bookings_read` | Api client read bookings | Reviewed fields only |
| `api_client.created` | Api client created | Reviewed fields only |
| `api_client.deleted` | Api client deleted | None declared |
| `api_client.participants_read` | Api client read participants | Reviewed fields only |
| `api_client.reactivated` | Api client reactivated | None declared |
| `api_client.revoked` | Api client revoked | None declared |
| `api_client.scopes_changed` | Api client scopes changed | Reviewed fields only |
| `api_client.secret_rotated` | Api client secret rotated | Reviewed fields only |
| `api_client.updated` | Api client updated | None declared |
| `api_integration.updated` | Api integration updated | None declared |
| `api_key_request.approved` | Api key request approved | Reviewed fields only |
| `api_key_request.created` | Api key request created | None declared |
| `api_key_request.rejected` | Api key request rejected | None declared |
| `asset.issued` | Asset issued | Reviewed fields only |
| `asset_units.generated` | Asset units generated | Reviewed fields only |
| `audit.signing_key_rotation_aborted` | Audit signing key rotation aborted | Withheld |
| `audit.signing_key_rotation_completed` | Audit signing key rotation completed | Withheld |
| `audit.signing_key_rotation_failed` | Audit signing key rotation failed | Withheld |
| `audit.signing_key_rotation_started` | Audit signing key rotation started | Withheld |
| `audit.verification_finished` | Audit verification finished | Reviewed fields only |
| `audit.verification_requested` | Audit verification requested | None declared |
| `auth.account_restore_intents_purged` | Expired account recovery intents removed | Withheld |
| `auth.captcha_failed` | CAPTCHA failed | Withheld |
| `auth.ip_auto_blocked` | Address blocked automatically | Withheld |
| `auth.ip_unblocked` | Address unblocked | Withheld |
| `auth.mfa_reset` | Two-step sign-in reset | Withheld |
| `auth.oidc_browser_attempt_consumed` | Auth oidc browser attempt consumed | Withheld |
| `auth.oidc_browser_attempt_started` | Auth oidc browser attempt started | Withheld |
| `auth.passkey_login_failed` | Passkey sign-in failed | Withheld |
| `auth.passkey_login_succeeded` | Signed in with a passkey | Withheld |
| `auth.passkey_registered` | Passkey added | Withheld |
| `auth.passkey_removed` | Passkey removed | Withheld |
| `auth.passkey_renamed` | Passkey renamed | Withheld |
| `auth.password_breach_rejected` | Breached password refused | Withheld |
| `auth.reauthentication_proofs_purged` | Auth reauthentication proofs purged | Withheld |
| `auth.social_identity_linked` | Auth social identity linked | Withheld |
| `auth.social_identity_unlinked` | Auth social identity unlinked | Withheld |
| `auth.staff_mfa_grace_started` | Staff two-step grace started | Withheld |
| `backup.archive_completed` | Backup archive completed | Reviewed fields only |
| `backup.archive_failed` | Backup archive failed | Reviewed fields only |
| `backup.archive_imported` | Backup archive imported | None declared |
| `backup.archive_key_job_queued` | Archive re-encryption or purge queued | Reviewed fields only |
| `backup.archive_pruned` | Backup archive pruned | None declared |
| `backup.archive_rehydrate_failed` | Backup archive rehydrate failed | None declared |
| `backup.archive_rehydrate_requested` | Backup archive rehydrate requested | None declared |
| `backup.archive_rehydrated` | Backup archive rehydrated | None declared |
| `backup.archive_requested` | Backup archive requested | Reviewed fields only |
| `backup.destination_created` | Backup destination created | Withheld |
| `backup.destination_probed` | Backup destination probed | Withheld |
| `backup.destination_retired` | Backup destination retired | None declared |
| `backup.destination_updated` | Backup destination updated | Withheld |
| `backup.download_url_issued` | Backup download url issued | Reviewed fields only |
| `backup.downloaded` | Backup downloaded | None declared |
| `backup.drill_completed` | Restore drill passed | Reviewed fields only |
| `backup.drill_failed` | Restore drill failed | Reviewed fields only |
| `backup.drill_requested` | Restore drill started from the console | None declared |
| `backup.offsite_copy_abandoned` | Backup offsite copy abandoned | None declared |
| `backup.offsite_copy_corrupted` | Backup offsite copy corrupted | None declared |
| `backup.offsite_copy_pruned` | Backup offsite copy pruned | None declared |
| `backup.offsite_copy_verified` | Backup offsite copy verified | None declared |
| `backup.offsite_push_requested` | Backup offsite push requested | None declared |
| `backup.operator_notice_sent` | Archive-ready notice sent | Reviewed fields only |
| `backup.platform_key_rotated` | Backup key rotation recorded | Reviewed fields only |
| `backup.purged` | Backup archive purged | Reviewed fields only |
| `backup.quarantine_acknowledged` | Backup quarantine acknowledged | Reviewed fields only |
| `backup.recovery_superadmin_established` | Backup recovery superadmin established | Reviewed fields only |
| `backup.reencrypt_cancelled` | Background re-encryption stopped | None declared |
| `backup.reencrypt_requested` | Background re-encryption started | None declared |
| `backup.reencrypted` | Backup archive re-encrypted to the current keys | Reviewed fields only |
| `backup.restore_completed` | Backup restore completed | None declared |
| `backup.restore_decided` | Backup restore decided | Reviewed fields only |
| `backup.restore_decision_expired` | Backup restore decision expired | Reviewed fields only |
| `backup.restore_quarantined` | Backup restore quarantined | Reviewed fields only |
| `backup.restore_requested` | Backup restore requested | Reviewed fields only |
| `backup.settings_updated` | Backup settings updated | Withheld |
| `backup.space_restore_aborted` | Space restore cancelled | Reviewed fields only |
| `backup.space_restore_completed` | Space restore completed | Reviewed fields only |
| `backup.space_restore_confirmed` | Space restore confirmed | Reviewed fields only |
| `backup.space_restore_failed` | Space restore failed | Reviewed fields only |
| `backup.space_restore_point_extracted` | Space restore point extracted from a whole-platform backup | Reviewed fields only |
| `backup.space_restore_preview_ready` | Space restore preview ready | Reviewed fields only |
| `backup.space_restore_requested` | Space restore requested | Reviewed fields only |
| `booking.broadcast.created` | Booking broadcast created | Withheld |
| `booking.cancelled_event_room_confirmed` | Booker confirmed cancelling a room that hosts an event | Withheld |
| `booking.departure_recorded` | Booking departure recorded | Withheld |
| `booking.feed_created` | Booking feed created | Withheld |
| `booking.feed_revoked` | Booking feed revoked | Withheld |
| `booking.feed_rotated` | Booking feed rotated | Withheld |
| `booking.included_hours_consumed` | Plan included hours used | Withheld |
| `booking.included_hours_restored` | Plan included hours restored | Withheld |
| `booking.issue_resolved` | Booking issue resolved | Withheld |
| `booking.org_hours_consumed` | Organization hours used | Withheld |
| `booking.org_hours_released` | Organization hours restored | Withheld |
| `booking.organization_linked` | Booking made for an organization | Withheld |
| `booking.pass_downloaded` | Booking pass downloaded | Withheld |
| `booking.pass_previewed` | Booking pass previewed | Withheld |
| `booking.pass_template_updated` | Booking pass template updated | Withheld |
| `booking.price_quoted_at_approval` | Booking charged at the approval-day price (no price frozen at request) | Withheld |
| `booking.recurrence_created` | Booking recurrence created | Withheld |
| `booking.replacement_created` | Replacement booking created | Withheld |
| `booking.space_photo_added` | Space photo added | Withheld |
| `booking.space_photo_removed` | Space photo removed | Withheld |
| `booking.space_photo_updated` | Space photo caption updated | Withheld |
| `booking.space_photos_reordered` | Space photos reordered | Withheld |
| `booking.space_rules_updated` | Booking space rules updated | Withheld |
| `box.assigned` | Box assigned | Reviewed fields only |
| `box.scanned` | Box scanned | Reviewed fields only |
| `calendar_feed.created` | Personal calendar link created | Reviewed fields only |
| `calendar_feed.revoked` | Personal calendar link revoked | Reviewed fields only |
| `calendar_feed.rotated` | Personal calendar link replaced | Reviewed fields only |
| `card.email_format_changed` | Card email format chosen | Reviewed fields only |
| `card.extras_optin_changed` | Card extras opt-in changed | Reviewed fields only |
| `card.photo_cleanup_accepted` | Cleaned card photo accepted | Reviewed fields only |
| `card.photo_cutout_choice` | Card photo cut-out or original chosen | Reviewed fields only |
| `card.photo_cutout_discarded` | Card photo cut-out discarded | Reviewed fields only |
| `card.photo_cutout_done` | Card photo cut-out ready | Reviewed fields only |
| `card.photo_cutout_failed` | Card photo background removal failed | Reviewed fields only |
| `card.photo_cutout_requested` | Card photo background removal requested | Reviewed fields only |
| `card.photo_requested` | New card photo requested | Reviewed fields only |
| `card.photo_set_by_staff` | Card photo set by staff (holder agreed) | Reviewed fields only |
| `card.scanned_for_checkin` | Card scanned to check in | Reviewed fields only |
| `card.verify_link_rotated` | Card check link rotated | Reviewed fields only |
| `card.verify_optin_changed` | Card check-page choices changed | Reviewed fields only |
| `card_design.approval_setting_changed` | Card design approval switch changed | Reviewed fields only |
| `card_design.approved` | Card design approved | Reviewed fields only |
| `card_design.archived` | Card design override archived | Reviewed fields only |
| `card_design.background_updated` | Card artwork uploaded | Reviewed fields only |
| `card_design.created` | Card design created | Reviewed fields only |
| `card_design.deleted` | Card design override deleted | Reviewed fields only |
| `card_design.exported` | Card design file exported | Reviewed fields only |
| `card_design.font_requested` | Card font download requested | Reviewed fields only |
| `card_design.imported` | Card design file imported | Reviewed fields only |
| `card_design.previewed_as_holder` | Card design previewed with a real holder | Reviewed fields only |
| `card_design.published` | Card design published | Reviewed fields only |
| `card_design.rejected` | Card design sent back | Reviewed fields only |
| `card_design.reset` | Card design reset to a template | Reviewed fields only |
| `card_design.restored` | Card design restored from an earlier version | Reviewed fields only |
| `card_design.saved` | Card design saved | Reviewed fields only |
| `card_design.submitted` | Card design submitted for approval | Reviewed fields only |
| `card_design.unarchived` | Card design override restored from the archive | Reviewed fields only |
| `card_design.watermark_updated` | Card watermark uploaded | Reviewed fields only |
| `card_job.cancelled` | Card job cancelled | Reviewed fields only |
| `card_job.failed` | Card job failed | Reviewed fields only |
| `card_job.previewed` | Print sheet previewed | Reviewed fields only |
| `card_job.queued` | Card job queued | Reviewed fields only |
| `card_job.result_downloaded` | Card job file downloaded | Reviewed fields only |
| `card_job.succeeded` | Card job finished | Reviewed fields only |
| `card_photo_batch.applied` | Bulk card photo upload applied | Reviewed fields only |
| `card_photo_batch.cancelled` | Bulk card photo upload cancelled | Reviewed fields only |
| `card_photo_batch.created` | Bulk card photo upload started | Reviewed fields only |
| `card_photo_batch.finished` | Bulk card photo upload finished | Reviewed fields only |
| `card_photo_batch.item_applied` | Bulk upload photo attached to a card | Reviewed fields only |
| `category.created` | Category created | Reviewed fields only |
| `category.deleted` | Category deleted | Reviewed fields only |
| `category.updated` | Category updated | None declared |
| `certification.granted` | Certification granted | Withheld |
| `certification.guest_granted` | Guest certification granted | Reviewed fields only |
| `certification.guest_revoked` | Guest certification revoked | Reviewed fields only |
| `certification.induction_linked` | Event marked as an induction | Reviewed fields only |
| `certification.induction_unlinked` | Induction marking removed | Withheld |
| `certification.override` | Certification override | Reviewed fields only |
| `certification.renewed` | Certification renewed | Withheld |
| `certification.revoked` | Certification revoked | Reviewed fields only |
| `certification_type.created` | Certification type created | Reviewed fields only |
| `certification_type.deactivated` | Certification type deactivated | None declared |
| `certification_type.updated` | Certification type updated | Reviewed fields only |
| `charge.free_by_pricing` | Nothing charged (free under pricing) | Reviewed fields only |
| `chat_template.deleted` | Chat template removed | Reviewed fields only |
| `chat_template.saved` | Chat template saved | Reviewed fields only |
| `cloud.delivery_cancelled` | Unknown delivery cancelled without replay | Reviewed fields only |
| `cloud.task_finished` | Cloud task finished | Reviewed fields only |
| `cloud.task_reconciled` | Cloud task reconciled | Reviewed fields only |
| `cloud.task_started` | Cloud task started | Reviewed fields only |
| `cloud.task_uncertain` | Cloud task uncertain | Reviewed fields only |
| `cloud.tick_finished` | Cloud tick finished | Reviewed fields only |
| `cloud.tick_history_pruned` | Cloud tick history pruned | Reviewed fields only |
| `cloud.tick_started` | Cloud tick started | Reviewed fields only |
| `consumable.cost_recorded` | Consumable cost recorded | None declared |
| `container.created` | Container created | None declared |
| `container.moved` | Container moved | None declared |
| `control.object_added` | Record added in /control/ | Reviewed fields only |
| `control.object_changed` | Record changed in /control/ | Reviewed fields only |
| `control.object_deleted` | Record deleted in /control/ | Reviewed fields only |
| `control.objects_deleted` | Records deleted in /control/ | Reviewed fields only |
| `data_export.completed` | Data export completed | Reviewed fields only |
| `data_export.download_url_issued` | Data export download url issued | Withheld |
| `data_export.downloaded` | Data export downloaded | Withheld |
| `data_export.failed` | Data export failed | Reviewed fields only |
| `data_export.requested` | Data export requested | Withheld |
| `deployment.capture_paused` | Deployment capture paused | Reviewed fields only |
| `deployment.capture_reconciled` | Deployment capture reconciled | Reviewed fields only |
| `deployment.capture_resumed` | Deployment capture resumed | Reviewed fields only |
| `deployment.managed_adopted` | Deployment managed adopted | Reviewed fields only |
| `deployment.managed_initialized` | Deployment managed initialized | Reviewed fields only |
| `deployment.staging_available` | Private staging verified | Reviewed fields only |
| `deployment.staging_created` | Private staging created | Reviewed fields only |
| `deployment.staging_deleted` | Private staging deletion confirmed | Reviewed fields only |
| `deployment.staging_retired` | Private staging retired | Reviewed fields only |
| `devices.adapter_command_leased` | Command delivered to a device adapter | Withheld |
| `devices.auth_artifacts_purged` | Devices auth artifacts purged | Withheld |
| `devices.integration_bound` | Machine integration bound to a type | Withheld |
| `devices.integration_unbound` | Machine integration removed | Withheld |
| `devices.integration_updated` | Machine integration changed | Withheld |
| `donation.campaign_created` | Donation campaign created | Reviewed fields only |
| `donation.campaign_updated` | Donation campaign changed | Reviewed fields only |
| `donation.cancelled` | Donation cancelled | Reviewed fields only |
| `donation.created` | Donation recorded | Reviewed fields only |
| `donation.exported` | Donations exported | Reviewed fields only |
| `donation.paid` | Donation received | Reviewed fields only |
| `donation.receipt_reissued` | Donation receipt sent again | Reviewed fields only |
| `donation.return_case_opened` | Refund case opened to return a gift | Reviewed fields only |
| `email.acceptance_reconciled` | Email provider acceptance reconciled | Reviewed fields only |
| `email.budget_deferred` | Email budget deferred | None declared |
| `email.budget_reserved` | Email budget reserved | None declared |
| `email.budget_settled` | Email budget settled | None declared |
| `email.notification_rules_updated` | Email notification rules updated | None declared |
| `email.platform_suppressed` | Platform email address suppressed | None declared |
| `email.platform_unsuppressed` | Platform email address suppression removed | None declared |
| `email.provider_event_received` | Email provider event received | None declared |
| `email.provider_observed` | Email provider observed | None declared |
| `email.redacted_proof_expired` | Email redacted proof expired | None declared |
| `email.retried` | Email retried | Reviewed fields only |
| `email.suppressed` | Email address suppressed | None declared |
| `email.suppressed_provider` | Email suppressed provider | None declared |
| `email.transport_tested` | Email transport tested | None declared |
| `email.unsuppressed` | Email address suppression removed | None declared |
| `email_template.reset` | Email template reset | Reviewed fields only |
| `email_template.type_reset` | Email template type reset | Withheld |
| `email_template.type_updated` | Email template type updated | Withheld |
| `email_template.updated` | Email template updated | Reviewed fields only |
| `encryption.emergency_rekey_completed` | Emergency re-key finished | Reviewed fields only |
| `encryption.emergency_rekey_started` | Emergency re-key started | Reviewed fields only |
| `encryption.key_job_failed` | Key job stopped | Reviewed fields only |
| `encryption.key_rotated` | Encryption key rotated | Reviewed fields only |
| `encryption.key_rotation_completed` | Encryption key rotation finished | Reviewed fields only |
| `encryption.platform_logs_redacted` | Encryption platform logs redacted | Reviewed fields only |
| `encryption.scoped_pii_decrypted` | Encryption scoped pii decrypted | Withheld |
| `encryption.search_key_bound` | Encryption search key bound | Reviewed fields only |
| `encryption.search_key_rotation_started` | Search key rotation started | Reviewed fields only |
| `encryption.search_key_verified` | Encryption search key verified | Reviewed fields only |
| `encryption.search_reindexed` | Search index rebuilt under a new key | Reviewed fields only |
| `encryption.write_fence_closed` | Encryption write fence closed | Reviewed fields only |
| `encryption.write_fence_opened` | Encryption write fence opened | Reviewed fields only |
| `equipment.context_linked` | Equipment linked to an event or booking | Reviewed fields only |
| `event.addon_created` | Ticket add-on created | Withheld |
| `event.addon_deleted` | Ticket add-on deleted | Withheld |
| `event.addon_updated` | Ticket add-on changed | Withheld |
| `event.admission_stage.assigned` | Reviewers assigned to a stage | Withheld |
| `event.admission_stage.created` | Review stage added | Withheld |
| `event.admission_stage.panel_changed` | Review stage panel changed | Withheld |
| `event.admission_stage.review_recused` | Stage reviewer recused | Withheld |
| `event.admission_stage.review_submitted` | Stage review submitted | Withheld |
| `event.admission_stage.updated` | Review stage changed | Withheld |
| `event.application.decision_skipped` | Stale application decision skipped | Withheld |
| `event.application.stage_advanced` | Application advanced to the next stage | Withheld |
| `event.approval_digest_sent` | Event approval digest sent | Withheld |
| `event.asset_abandoned` | Event asset abandoned | Withheld |
| `event.asset_attempt_failed` | Event asset attempt failed | Withheld |
| `event.asset_budget_changed` | Event asset budget changed | Withheld |
| `event.asset_bytes_deleted` | Event asset bytes deleted | Withheld |
| `event.asset_expired` | Event asset expired | Withheld |
| `event.asset_promoting` | Event asset promoting | Withheld |
| `event.asset_quarantined` | Event asset quarantined | Withheld |
| `event.asset_ready` | Event asset ready | Withheld |
| `event.asset_reserved` | Event asset reserved | Withheld |
| `event.asset_retention_anchored` | Event asset retention anchored | Withheld |
| `event.asset_upload_refreshed` | Event asset upload refreshed | Withheld |
| `event.asset_uploaded` | Event asset uploaded | Withheld |
| `event.asset_uploading` | Event asset uploading | Withheld |
| `event.asset_usage_reconciled` | Event storage usage reconciled | Withheld |
| `event.asset_validating` | Event asset validating | Withheld |
| `event.attendance.replied` | Attendance reply received | Withheld |
| `event.attendance.sent` | Attendance confirmation sent | Withheld |
| `event.audience_updated` | Event audience updated | Withheld |
| `event.badge_design_previewed` | Event badge design previewed | Withheld |
| `event.badge_design_saved` | Event badge design saved | Withheld |
| `event.badge_logo_reserved` | Event badge logo reserved | Withheld |
| `event.badge_pdf_reserved` | Event badge pdf reserved | Withheld |
| `event.badge_print_cancelled` | Event badge print cancelled | Withheld |
| `event.badge_print_claimed` | Event badge print claimed | Withheld |
| `event.badge_print_cleaned` | Event badge print cleaned | Withheld |
| `event.badge_print_downloaded` | Event badge print downloaded | Withheld |
| `event.badge_print_failed` | Event badge print failed | Withheld |
| `event.badge_print_ready` | Event badge print ready | Withheld |
| `event.badge_print_requested` | Event badge print requested | Withheld |
| `event.badge_resource_bound` | Event badge resource bound | Withheld |
| `event.badge_template_updated` | Event badge template updated | Withheld |
| `event.badges_generated` | Event badges generated | Withheld |
| `event.booking_decision_linked` | Room booking linked to the event | Withheld |
| `event.booking_decision_partial_coverage` | Room booking linked with partial time coverage | Withheld |
| `event.booking_decision_replaced` | Linked room booking replaced | Withheld |
| `event.broadcast.cancelled` | Event broadcast cancelled | Withheld |
| `event.broadcast.created` | Event broadcast created | Withheld |
| `event.broadcast.previewed` | Event broadcast previewed | Withheld |
| `event.broadcast.scheduled` | Event broadcast scheduled | Withheld |
| `event.broadcast.test_queued` | Event broadcast test queued | Withheld |
| `event.broadcast_cancelled_in_hold` | Event broadcast undone inside its hold | Withheld |
| `event.broadcast_draft_saved` | Event broadcast draft saved | Withheld |
| `event.broadcast_held` | Event broadcast sent with a five-second undo hold | Withheld |
| `event.calendar_feed_created` | Event calendar feed created | Withheld |
| `event.calendar_feed_revoked` | Event calendar feed revoked | Withheld |
| `event.calendar_feed_rotated` | Event calendar feed rotated | Withheld |
| `event.category_created` | Event category created | Withheld |
| `event.category_deleted` | Event category deleted | Withheld |
| `event.category_updated` | Event category updated | Withheld |
| `event.certificate_artwork_presigned` | Certificate artwork upload reserved | Withheld |
| `event.certificate_artwork_promoted` | Certificate artwork promoted | Withheld |
| `event.certificate_batch_completed` | Event certificate batch completed | Withheld |
| `event.certificate_batch_created` | Event certificate batch created | Withheld |
| `event.certificate_batch_item_processed` | Event certificate batch item processed | Withheld |
| `event.certificate_batch_started` | Event certificate batch started | Withheld |
| `event.certificate_created` | Event certificate created | Withheld |
| `event.certificate_design_approved` | Certificate design approved by a signatory | Withheld |
| `event.certificate_downloaded` | Event certificate downloaded | Withheld |
| `event.certificate_holder_name_changed` | Certificate holder name visibility changed | Withheld |
| `event.certificate_library_artwork_copied` | Event certificate library artwork copied | Withheld |
| `event.certificate_library_artwork_promoted` | Event certificate library artwork promoted | Withheld |
| `event.certificate_library_artwork_reserved` | Event certificate library artwork reserved | Withheld |
| `event.certificate_library_capture_completed` | Event certificate library capture completed | Withheld |
| `event.certificate_library_capture_promoted` | Event certificate library capture promoted | Withheld |
| `event.certificate_library_capture_reserved` | Event certificate library capture reserved | Withheld |
| `event.certificate_library_capture_started` | Event certificate library capture started | Withheld |
| `event.certificate_library_copy_reserved` | Event certificate library copy reserved | Withheld |
| `event.certificate_library_saved` | Event certificate library saved | Withheld |
| `event.certificate_png_downloaded` | Event certificate image downloaded | Withheld |
| `event.certificate_publication_enabled` | Event certificate publication enabled | Withheld |
| `event.certificate_reissued` | Event certificate reissued | Withheld |
| `event.certificate_render_claimed` | Event certificate render claimed | Withheld |
| `event.certificate_render_failed` | Event certificate render failed | Withheld |
| `event.certificate_rendered` | Event certificate rendered | Withheld |
| `event.certificate_requested` | Event certificate requested | Withheld |
| `event.certificate_revoked` | Event certificate revoked | Withheld |
| `event.certificate_seed_artwork_reserved` | Event default design artwork reserved | Withheld |
| `event.certificate_share_image_downloaded` | Event certificate share image downloaded | Withheld |
| `event.certificate_signatory_approval_policy_changed` | Certificate signatory approval switched | Withheld |
| `event.certificate_signatory_removed` | Certificate signatory removed | Withheld |
| `event.certificate_signatory_saved` | Certificate signatory added or changed | Withheld |
| `event.certificate_template_previewed` | Certificate template previewed | Withheld |
| `event.certificate_template_saved` | Certificate template revision saved | Withheld |
| `event.certificate_verification_changed` | Event certificate verification changed | Withheld |
| `event.certificate_verification_policy_changed` | Event certificate verification policy changed | Withheld |
| `event.checkin_list.archived` | Check-in list archived | Withheld |
| `event.checkin_list.created` | Check-in list created | Withheld |
| `event.checkin_list.scanned` | Collected from a check-in list | Withheld |
| `event.checkin_list.updated` | Check-in list changed | Withheld |
| `event.collaboration_accepted` | Event collaboration accepted | Withheld |
| `event.collaboration_declined` | Event collaboration declined | Withheld |
| `event.collaborators_changed` | Event collaborators changed | Withheld |
| `event.contributor_notice.claimed` | Event contributor notice claimed | Withheld |
| `event.contributor_notice.delivered` | Event contributor notice delivered | Withheld |
| `event.contributor_notice.retry` | Event contributor notice retry | Withheld |
| `event.created_with_room` | Event created with a room step | Withheld |
| `event.credential_issued` | Event credential issued | Withheld |
| `event.credential_revoked` | Event credential revoked | Withheld |
| `event.crew.approved` | Crew member approved | Withheld |
| `event.crew.declined` | Crew sign-up declined | Withheld |
| `event.crew.place_created` | Crew place given | Withheld |
| `event.crew.place_released` | Crew place released | Withheld |
| `event.crew.removed` | Crew member removed | Withheld |
| `event.crew.signed_up` | Crew sign-up received | Withheld |
| `event.crew.withdrawn` | Crew member withdrew | Withheld |
| `event.delivery_mode_changed` | Event delivery mode changed | Withheld |
| `event.deposit.forfeited` | Deposit kept after a no-show | Withheld |
| `event.deposit.settled` | Event deposits settled by staff | Withheld |
| `event.embed_policy_updated` | Event embed allow-list updated | Withheld |
| `event.entitlement.created` | Event entitlement created | Withheld |
| `event.entitlement.revoked` | Event entitlement revoked | Withheld |
| `event.equipment_planned` | Equipment planned for event participants | Withheld |
| `event.equipment_return_window_changed` | Event equipment return window changed | Withheld |
| `event.export.csv` | Event list exported as CSV | Withheld |
| `event.feedback_anonymous_enabled` | Event feedback set to anonymous | Withheld |
| `event.feedback_submitted` | Event feedback submitted | Withheld |
| `event.feedback_survey_closed` | Event feedback survey closed | Withheld |
| `event.feedback_survey_configured` | Event feedback survey configured | Withheld |
| `event.feedback_survey_opened` | Event feedback survey opened | Withheld |
| `event.form_revised` | Event form revised | Withheld |
| `event.hackathon.retention_anchored` | Event submission retention anchored | Withheld |
| `event.hackathon.team_exception_granted` | Event hackathon team exception granted | Withheld |
| `event.hackathon.team_locked` | Event hackathon team locked | Withheld |
| `event.hackathon.team_reopened` | Event hackathon team reopened | Withheld |
| `event.help.attention` | Event help attention | Withheld |
| `event.help.cancelled_with_event` | Event help cancelled with event | Withheld |
| `event.help.round_triggered` | Event help round triggered | Withheld |
| `event.host_waiver_accepted` | Event host waiver accepted | Withheld |
| `event.image_removed` | Event image removed | Withheld |
| `event.image_updated` | Event image updated | Withheld |
| `event.invitations_added` | Event invitations added | Withheld |
| `event.judging.finalists_advanced` | Finalists advanced to the next round | Withheld |
| `event.judging.finalists_published` | Finalists published | Withheld |
| `event.mentor.assignment.ended_with_role` | Event mentor assignment ended with role | Withheld |
| `event.mentor_mappings.exported` | Event mentor mappings exported | Withheld |
| `event.mentor_notice.claimed` | Event mentor notice claimed | Withheld |
| `event.mentor_notice.delivered` | Event mentor notice delivered | Withheld |
| `event.mentor_notice.retry` | Event mentor notice retry | Withheld |
| `event.office_hours.cancelled` | Event office hours cancelled | Withheld |
| `event.order_attendees_updated` | Order attendees updated | Withheld |
| `event.order_cancelled` | Ticket order cancelled | Withheld |
| `event.order_created` | Ticket order placed | Withheld |
| `event.order_due_opened` | Refund owed on a ticket order | Withheld |
| `event.order_expired` | Ticket checkout expired | Withheld |
| `event.order_paid` | Ticket order paid | Withheld |
| `event.order_seat_cancelled` | Order seat cancelled | Withheld |
| `event.order_unfulfilled` | Paid order could not be seated | Withheld |
| `event.organizers_updated` | Event organizers updated | Withheld |
| `event.participation_settings_updated` | Event participation switches changed | Withheld |
| `event.pass_occurrence_cancelled` | Pass occurrence cancelled | Withheld |
| `event.pass_order_created` | Series pass ordered | Withheld |
| `event.pass_type_saved` | Series pass type saved | Withheld |
| `event.pay_link_issued` | Ticket pay link issued | Withheld |
| `event.payment_collected_at_desk` | Ticket payment collected at the desk | Withheld |
| `event.peoples_choice.ballot_cast` | People's choice vote cast or changed | Withheld |
| `event.peoples_choice.published` | People's choice result published | Withheld |
| `event.peoples_choice.updated` | People's choice settings changed | Withheld |
| `event.peoples_choice.vote_voided` | People's choice vote voided | Withheld |
| `event.presentation_updated` | Event presentation updated | Withheld |
| `event.prize.claim_removed` | Prize payee details removed | Withheld |
| `event.prize.claim_revealed` | Prize payee details revealed to pay the winner | Withheld |
| `event.prize.claim_submitted` | Prize payee details given | Withheld |
| `event.prize.claim_verified` | Prize payee details verified | Withheld |
| `event.prize.forfeited` | Unclaimed prize forfeited | Withheld |
| `event.prize.fulfilled` | Non-cash prize handed over or shipped | Withheld |
| `event.prize.payout_recorded` | Prize payout recorded | Withheld |
| `event.prize.payout_reversed` | Prize payout reversed | Withheld |
| `event.prize.recovery_opened` | Prize money owed back after a disqualification | Withheld |
| `event.prize.recovery_repaid` | Prize money repaid | Withheld |
| `event.prize.recovery_waived` | Prize money recovery waived | Withheld |
| `event.prize.share_confirmed` | Prize share confirmed | Withheld |
| `event.prize.share_declined` | Prize share declined | Withheld |
| `event.prize.split_proposed` | Prize split proposed by the team leader | Withheld |
| `event.prize.split_recorded` | Prize split recorded by staff | Withheld |
| `event.prize.sponsor_paid` | Prize paid directly by the sponsor | Withheld |
| `event.programme.contribution_definitions_copied` | Event contribution definitions copied | Withheld |
| `event.programme.definitions_copied` | Event programme definitions copied | Withheld |
| `event.programme_options.updated` | Event programme options changed | Withheld |
| `event.publishing_changed` | Event publishing changed | Withheld |
| `event.refund_policy_overridden` | Event refund policy changed | Withheld |
| `event.registration_calendar_downloaded` | Event registration calendar downloaded | Withheld |
| `event.reimbursement.claim_cancelled` | Event reimbursement claim cancelled | Withheld |
| `event.reimbursement.module_purge_no_liability` | Event reimbursement module purge no liability | Withheld |
| `event.reimbursement.requested` | Event reimbursement requested | Withheld |
| `event.results_email.sent` | Results email sent | Withheld |
| `event.role.cancelled_with_event` | Event contribution cancelled with event | Withheld |
| `event.role.host_waiver_accepted` | Event role host waiver accepted | Withheld |
| `event.role.owner_exported` | Event role owner exported | Withheld |
| `event.sales_settings_updated` | Event sales rules changed | Withheld |
| `event.seat_claimed` | Seat claimed | Withheld |
| `event.seat_invited` | Seat claim invite sent | Withheld |
| `event.series_audience_updated` | Event series audience updated | Withheld |
| `event.series_cancelled` | Event series cancelled | Withheld |
| `event.series_collaboration_accepted` | Event series collaboration accepted | Withheld |
| `event.series_collaboration_declined` | Event series collaboration declined | Withheld |
| `event.series_collaborators_changed` | Event series collaborators changed | Withheld |
| `event.series_completed` | Event series completed | Withheld |
| `event.series_created` | Event series created | Withheld |
| `event.series_extended` | Event series extended | Withheld |
| `event.series_generation_failed` | Event series generation failed | Withheld |
| `event.series_image_removed` | Event series image removed | Withheld |
| `event.series_image_updated` | Event series image updated | Withheld |
| `event.series_occurrence_created` | Event series occurrence created | Withheld |
| `event.series_occurrence_removed` | Event series occurrence removed | Withheld |
| `event.series_organizer_created` | Event series organizer created | Withheld |
| `event.series_organizer_deleted` | Event series organizer deleted | Withheld |
| `event.series_organizer_updated` | Event series organizer updated | Withheld |
| `event.series_published` | Event series published | Withheld |
| `event.series_updated` | Event series updated | Withheld |
| `event.shift.waitlist_promoted` | Event shift waitlist promoted | Withheld |
| `event.shift.withdrawn_with_role` | Event shift withdrawn with role | Withheld |
| `event.short_link.created` | Event short link created | Withheld |
| `event.short_link.regenerated` | Event short link regenerated | Withheld |
| `event.speaker_assigned` | Event speaker assigned | Withheld |
| `event.speaker_claimed` | Event speaker invitation claimed | Withheld |
| `event.speaker_invited` | Event speaker invited | Withheld |
| `event.speaker_removed` | Event speaker removed | Withheld |
| `event.staff_grant_container_created` | Event permission container created | Withheld |
| `event.staff_grant_manual_revoked` | Event manual permissions revoked | Withheld |
| `event.stage_file.attached` | Event stage file attached | Withheld |
| `event.stage_file.deleted` | Event stage file deleted | Withheld |
| `event.stage_file.expired` | Event stage file expired | Withheld |
| `event.stage_file.validating` | Event stage file validating | Withheld |
| `event.stage_file.validation_result` | Event stage file validation result | Withheld |
| `event.stage_form.activation_cancelled` | Event stage form activation cancelled | Withheld |
| `event.stage_form.activation_progress` | Event stage form activation progress | Withheld |
| `event.stage_form.assigned` | Event stage form assigned | Withheld |
| `event.stage_form.cancelled` | Event stage form cancelled | Withheld |
| `event.stage_form.date_context_changed` | Event stage form date context changed | Withheld |
| `event.stage_form.draft_saved` | Event stage form draft saved | Withheld |
| `event.stage_form.import_reactivated` | Event stage form import reactivated | Withheld |
| `event.stage_form.next_stage_locked` | Event stage form next stage locked | Withheld |
| `event.stage_form.opened` | Event stage form opened | Withheld |
| `event.stage_form.overdue` | Event stage form overdue | Withheld |
| `event.stage_form.rescheduled` | Event stage form rescheduled | Withheld |
| `event.stage_form.response_locked` | Event stage form response locked | Withheld |
| `event.stage_form.response_recovered` | Event stage form response recovered | Withheld |
| `event.stage_form.submitted` | Event stage form submitted | Withheld |
| `event.submission_integrity_flagged` | Event submission integrity flagged | Withheld |
| `event.submission_locked` | Event submission locked | Withheld |
| `event.submission_review_transition` | Event submission review transition | Withheld |
| `event.submission_stage.extension_granted` | Stage deadline extended for a team | Withheld |
| `event.submission_stage.shortlist_applied` | Stage shortlist chosen | Withheld |
| `event.submission_stage.shortlist_promoted` | Next team promoted onto a stage shortlist | Withheld |
| `event.submission_stage.shortlist_published` | Stage shortlist published | Withheld |
| `event.submission_stages.updated` | Submission stages changed | Withheld |
| `event.submission_triaged` | Event submission triaged | Withheld |
| `event.ticket_deleted` | Event ticket type deleted | Withheld |
| `event.ticket_downloaded` | Event ticket downloaded | Withheld |
| `event.ticket_template_created` | Event ticket template created | Withheld |
| `event.ticket_transfer_offered` | Ticket transfer offered | Withheld |
| `event.ticket_transferred` | Ticket transferred | Withheld |
| `event.ticket_type_changed` | Ticket type changed | Withheld |
| `event.ticket_updated` | Event ticket type updated | Withheld |
| `event.venue_fee_charged` | Venue fee charged | Withheld |
| `event.venue_fee_configured` | Venue fee set | Withheld |
| `event.website_unattached_assets_removed` | Unattached event website images removed | Withheld |
| `event.workshop_machine_linked` | Workshop machine booking linked to the event | Withheld |
| `event.workshop_machine_replaced` | Linked workshop machine booking replaced | Withheld |
| `event.workshop_machine_unlinked` | Workshop machine booking unlinked from the event | Withheld |
| `event_card.downloaded` | Event ID card downloaded | Reviewed fields only |
| `event_card.emailed` | Event ID card emailed | Reviewed fields only |
| `event_card.extras_access_changed` | First-aid card details access changed | Reviewed fields only |
| `event_card.extras_viewed` | First-aid card details viewed | Reviewed fields only |
| `event_card.issued` | Event ID card issued | Reviewed fields only |
| `event_card.photo_removed` | Event ID card photo removed | Reviewed fields only |
| `event_card.photo_updated` | Event ID card photo updated | Reviewed fields only |
| `event_card.revoked` | Event ID card revoked | Reviewed fields only |
| `event_card.role_changed` | Event ID card role changed | Reviewed fields only |
| `events.answers.date_review_requested` | Events answers date review requested | Withheld |
| `events.answers.date_reviewed` | Events answers date reviewed | Withheld |
| `events.answers.draft_source_deleted` | Events answers draft source deleted | Withheld |
| `events.answers.draft_source_erased` | Events answers draft source erased | Withheld |
| `events.answers.locked` | Events answers locked | Withheld |
| `events.answers.purged` | Events answers purged | None declared |
| `events.answers.reopened` | Events answers reopened | Withheld |
| `events.answers.source_saved` | Events answers source saved | Withheld |
| `evidence.abandoned_upload_deleted` | Evidence abandoned upload deleted | Withheld |
| `evidence.attached` | Evidence attached | Reviewed fields only |
| `evidence.object_expired` | Evidence object expired | Reviewed fields only |
| `evidence.retention_policy_updated` | Evidence retention policy updated | Reviewed fields only |
| `evidence.upload_url_issued` | Evidence upload url issued | Withheld |
| `evidence.viewed` | Evidence viewed | None declared |
| `finance.attachment.attached` | Finance attachment attached | None declared |
| `finance.attachment.bound` | Finance attachment bound | None declared |
| `finance.attachment.cleanup_complete` | Finance attachment cleanup complete | Withheld |
| `finance.attachment.cleanup_retry` | Finance attachment cleanup retry | Withheld |
| `finance.attachment.closed` | Finance attachment closed | None declared |
| `finance.attachment.closure_preserved` | Finance attachment closure preserved | None declared |
| `finance.attachment.deleted` | Finance attachment deleted | None declared |
| `finance.attachment.discarded` | Finance attachment discarded | None declared |
| `finance.attachment.duplicate` | Finance attachment duplicate | Withheld |
| `finance.attachment.expired` | Finance attachment expired | None declared |
| `finance.attachment.held` | Finance attachment held | Withheld |
| `finance.attachment.hold_released` | Finance attachment hold released | Withheld |
| `finance.attachment.initiated` | Finance attachment initiated | None declared |
| `finance.attachment.opened` | Finance attachment opened | None declared |
| `finance.attachment.ready` | Finance attachment ready | Withheld |
| `finance.attachment.reopened` | Finance attachment reopened | None declared |
| `finance.attachment.upload_completed` | Finance attachment upload completed | None declared |
| `finance.attachment.validation_failed` | Finance attachment validation failed | None declared |
| `finance.attachment.validation_started` | Finance attachment validation started | None declared |
| `finance.event_payout.amended` | Finance event payout amended | Withheld |
| `finance.event_payout.annual_review_due` | Event payout annual review due | None declared |
| `finance.event_payout.cancelled` | Event payout cancelled | None declared |
| `finance.event_payout.decision_recorded` | Event payout decision recorded | None declared |
| `finance.event_payout.detached` | Event payout detached | None declared |
| `finance.event_payout.eligibility_changed` | Event payout eligibility changed | None declared |
| `finance.event_payout.export_created` | Event payout export created | None declared |
| `finance.event_payout.export_downloaded` | Event payout export downloaded | None declared |
| `finance.event_payout.held` | Event payout held | Withheld |
| `finance.event_payout.hold_released` | Finance event payout hold released | Withheld |
| `finance.event_payout.payee_closed` | Event payout payee closed | None declared |
| `finance.event_payout.payee_correction` | Finance event payout payee correction | Withheld |
| `finance.event_payout.payee_purged` | Event payout payee purged | None declared |
| `finance.event_payout.payee_reopened` | Event payout payee reopened | None declared |
| `finance.event_payout.payee_revealed` | Event payout payee revealed | None declared |
| `finance.event_payout.payee_submitted` | Event payout payee submitted | None declared |
| `finance.event_payout.payee_verified` | Finance event payout payee verified | Withheld |
| `finance.event_payout.recorded` | Finance event payout recorded | Withheld |
| `finance.event_payout.settlement_projected` | Event payout settlement projected | None declared |
| `finance.retention_policy.changed` | Finance retention policy changed | None declared |
| `hosting_request.accepted` | Hosting request accepted | None declared |
| `hosting_request.changes_requested` | Hosting request: changes requested | None declared |
| `hosting_request.invitation_answered` | Hosting invitation answered | None declared |
| `hosting_request.invitation_cancelled` | Hosting invitation cancelled | None declared |
| `hosting_request.invitation_created` | Hosting invitation created | Reviewed fields only |
| `hosting_request.makerspace_linked` | Makerspace created from hosting request | Reviewed fields only |
| `hosting_request.rejected` | Hosting request rejected | None declared |
| `hosting_request.resubmitted` | Hosting request resubmitted | Reviewed fields only |
| `hosting_request.submitted` | Hosting request submitted | Reviewed fields only |
| `id_programme.archived` | ID programme archived | Reviewed fields only |
| `id_programme.card_added` | Person added to an ID programme | Reviewed fields only |
| `id_programme.card_deleted` | ID card deleted | Reviewed fields only |
| `id_programme.card_downloaded` | ID card downloaded | Reviewed fields only |
| `id_programme.card_emailed` | ID card emailed | Reviewed fields only |
| `id_programme.card_linked` | ID card linked to an account | Reviewed fields only |
| `id_programme.card_photo_removed` | ID card photo removed | Reviewed fields only |
| `id_programme.card_photo_updated` | ID card photo updated | Reviewed fields only |
| `id_programme.card_requested` | ID card requested | Reviewed fields only |
| `id_programme.card_updated` | ID card details changed | Reviewed fields only |
| `id_programme.cards_approved` | ID cards approved | Reviewed fields only |
| `id_programme.cards_imported` | ID cards imported | Reviewed fields only |
| `id_programme.cards_reinstated` | ID cards reinstated | Reviewed fields only |
| `id_programme.cards_rejected` | ID card requests not approved | Reviewed fields only |
| `id_programme.cards_renewed` | ID cards renewed | Reviewed fields only |
| `id_programme.cards_revoked` | ID cards revoked | Reviewed fields only |
| `id_programme.closed` | ID programme closed | Reviewed fields only |
| `id_programme.created` | ID programme created | Reviewed fields only |
| `id_programme.deleted` | ID programme deleted | Reviewed fields only |
| `id_programme.fields_updated` | ID programme questions changed | Reviewed fields only |
| `id_programme.unarchived` | ID programme restored from the archive | Reviewed fields only |
| `id_programme.updated` | ID programme changed | Reviewed fields only |
| `image_adapter.platform_switch` | Platform eraser fallback switched | Reviewed fields only |
| `image_adapter.removed` | Eraser provider removed | Reviewed fields only |
| `image_adapter.rotated` | Eraser provider secret rotated | Reviewed fields only |
| `image_adapter.saved` | Eraser provider saved | Reviewed fields only |
| `image_adapter.tested` | Eraser provider tested | Reviewed fields only |
| `incident.action_added` | Incident follow-up action added | Reviewed fields only |
| `incident.action_done` | Incident follow-up action updated | Reviewed fields only |
| `incident.reported` | Incident reported | Withheld |
| `incident.status_changed` | Incident status changed | Withheld |
| `incident.updated` | Incident updated | Withheld |
| `inventory.asset_moved_makerspace` | Inventory asset moved makerspace | Reviewed fields only |
| `inventory.asset_updated` | Inventory asset updated | Reviewed fields only |
| `inventory.bulk_import_sheet_read` | Inventory import spreadsheet read | Reviewed fields only |
| `inventory.bulk_imported` | Inventory bulk imported | Reviewed fields only |
| `inventory.created` | Inventory created | None declared |
| `inventory.equipment_consumable_plan_created` | Consumable plan created | None declared |
| `inventory.equipment_kit_changed` | Equipment kit setting changed | Reviewed fields only |
| `inventory.equipment_kit_created` | Equipment kit created | Reviewed fields only |
| `inventory.equipment_kit_version_created` | Equipment kit version created | Reviewed fields only |
| `inventory.image_attached` | Inventory image attached | Withheld |
| `inventory.image_cleared` | Inventory image cleared | Withheld |
| `inventory.quantity_adjusted` | Inventory quantity adjusted | Reviewed fields only |
| `inventory.renamed` | Inventory renamed | None declared |
| `inventory.stock_observed` | Inventory stock observed | None declared |
| `inventory.updated` | Inventory updated | None declared |
| `inventory.waitlist_claimed` | Waitlist offer claimed | Reviewed fields only |
| `inventory.waitlist_joined` | Joined a waitlist | Reviewed fields only |
| `inventory.waitlist_lapsed` | Waitlist offer lapsed | Reviewed fields only |
| `inventory.waitlist_left` | Left a waitlist | Reviewed fields only |
| `inventory.waitlist_offered` | Waitlist offer held | Reviewed fields only |
| `inventory.watch_notified` | Inventory watch notified | None declared |
| `inventory.watch_subscribed` | Inventory watch subscribed | None declared |
| `inventory.watch_unsubscribed` | Inventory watch unsubscribed | None declared |
| `invitation_request.declined` | Invitation request declined | Reviewed fields only |
| `invitation_request.invited` | Invitation request invited | Reviewed fields only |
| `invitation_request.submitted` | Invitation request submitted | Reviewed fields only |
| `issue.dispatched` | Issue sent to technicians | Reviewed fields only |
| `kiosk.online_command_executed` | Kiosk online command executed | Withheld |
| `kiosk.operator_lease_issued` | Kiosk operator lease issued | Withheld |
| `kiosk.operator_lease_revoked` | Kiosk operator lease revoked | Withheld |
| `kiosk.replay_claimed` | Kiosk replay claimed | Withheld |
| `kiosk.replay_failed` | Kiosk replay failed | Withheld |
| `kiosk.replay_prepared` | Kiosk replay prepared | Withheld |
| `kiosk.replay_resolved` | Kiosk replay resolved | Withheld |
| `kiosk.replay_succeeded` | Kiosk replay succeeded | Withheld |
| `kiosk.station_created` | Kiosk station created | Withheld |
| `kiosk.station_disabled` | Kiosk station disabled | Withheld |
| `kiosk.station_pin_failed` | Kiosk station pin failed | Withheld |
| `kiosk.station_pin_revealed` | Kiosk station pin revealed | Withheld |
| `kiosk.station_pin_rotated` | Kiosk station pin rotated | Withheld |
| `kiosk.station_session_ended` | Kiosk station session ended | Reviewed fields only |
| `kiosk.station_session_started` | Kiosk station session started | Withheld |
| `kiosk.work_package_issued` | Kiosk work package issued | Withheld |
| `kit.component_missing` | Kit component missing | None declared |
| `kit.issue_recorded` | Kit issue checklist recorded | None declared |
| `kit.return_recorded` | Kit return checklist recorded | None declared |
| `ledger.entry_created` | Other receipt recorded | Reviewed fields only |
| `ledger.entry_voided` | Ledger entry voided | Reviewed fields only |
| `ledger.event_budget_set` | Event budget set | Reviewed fields only |
| `ledger.expense_recorded` | Expense recorded | Reviewed fields only |
| `ledger.opening_balance_set` | Opening balance set | Reviewed fields only |
| `loan.accountability_not_charged` | Damage or loss recorded with no charge | Reviewed fields only |
| `loan.booking_context_changed` | Loan booking context changed | Reviewed fields only |
| `loan.damage_charged` | Damage charge raised | Reviewed fields only |
| `loan.deposit_raised` | Loan deposit raised | Reviewed fields only |
| `loan.event_context_changed` | Loan event context changed | Reviewed fields only |
| `loan.fee_waived` | Loan fees waived | Reviewed fields only |
| `loan.fee_waiver_revoked` | Loan fee waiver revoked | Reviewed fields only |
| `loan.late_fee_raised` | Loan late fee raised | Reviewed fields only |
| `loan.lost_charged` | Lost item charge raised | Reviewed fields only |
| `loan.rental_deferred` | Loan rental to be charged at return | Reviewed fields only |
| `loan.rental_raised` | Loan rental raised | Reviewed fields only |
| `machine.created` | Machine created | Withheld |
| `machine.intake_updated` | Machine intake updated | Withheld |
| `machine.material_created` | Machine material created | Withheld |
| `machine.material_deleted` | Machine material deleted | Withheld |
| `machine.material_updated` | Machine material updated | Withheld |
| `machine.open_access_changed` | Machine open to all members changed | Withheld |
| `machine.publicity_changed` | Machine publicity changed | Withheld |
| `machine_access.granted` | Machine access granted | Withheld |
| `machine_access.renewed` | Machine access renewed | Withheld |
| `machine_access.revoked` | Machine access revoked | Withheld |
| `machine.status_changed` | Machine status changed | Withheld |
| `machine.typed_usage_logged` | Machine typed usage logged | Withheld |
| `machine.updated` | Machine updated | Withheld |
| `machine_downtime.ended` | Machine back in service | Reviewed fields only |
| `machine_downtime.started` | Machine out of service | Reviewed fields only |
| `machine_downtime.updated` | Downtime details updated | Reviewed fields only |
| `machine_service.agent_report_applied` | Printer report applied to a service job | Withheld |
| `machine_service.agent_report_refused` | Printer report refused | Withheld |
| `machine_service.consumable_stock_short` | Job consumable stock ran short | Reviewed fields only |
| `machine_service.consumables_estimated` | Job consumables estimated | Reviewed fields only |
| `machine_service.consumables_recorded` | Job consumables recorded | Reviewed fields only |
| `machine_service.consumption_recorded` | Machine service consumption recorded | Withheld |
| `machine_service.file_attached` | Machine service file attached | Withheld |
| `machine_service.file_deleted` | Machine service file deleted | Withheld |
| `machine_service.file_staged` | Machine service file staged | Withheld |
| `machine_event.changed` | Machine use event changed | Reviewed fields only |
| `machine_event.cleared` | Machine use event cleared | Reviewed fields only |
| `machine_event.cost_approved` | Machine cost approved for the event | Reviewed fields only |
| `machine_event.cost_withdrawn` | Machine cost approval withdrawn | Reviewed fields only |
| `machine_event.linked` | Machine use linked to an event | Reviewed fields only |
| `machine_session.amended` | Machine session time corrected | Reviewed fields only |
| `machine_session.assigned` | Machine session assigned to a member | Reviewed fields only |
| `machine_session.auto_stopped` | Machine session stopped automatically | Reviewed fields only |
| `machine_session.charge_raised` | Machine session charge raised | Reviewed fields only |
| `machine_session.confirmed` | Machine session confirmed | Reviewed fields only |
| `machine_session.device_skipped` | Device session not opened | Reviewed fields only |
| `machine_session.started` | Machine session started | Reviewed fields only |
| `machine_session.stopped` | Machine session stopped | Reviewed fields only |
| `machine_session.supervised_closed` | Supervised session closed | Withheld |
| `machine_session.supervised_opened` | Supervised session opened | Withheld |
| `machine_session.supervised_use_ended` | Supervised use ended | Withheld |
| `machine_session.supervised_use_started` | Supervised use started | Withheld |
| `machine_session.supervisee_added` | Supervisee added | Withheld |
| `machine_session.supervisee_removed` | Supervisee removed | Withheld |
| `machine_type.created` | Machine type created | None declared |
| `machine_type.job_settings_updated` | Machine type job settings changed | Reviewed fields only |
| `machine_type.policy_updated` | Machine type policy updated | None declared |
| `machine_type.session_settings_updated` | Machine type session settings changed | Reviewed fields only |
| `machine_type.template_applied` | Machine type template applied | Reviewed fields only |
| `machine_type.updated` | Machine type updated | None declared |
| `machine_type_consumable.created` | Consumable added to a machine type | Reviewed fields only |
| `machine_type_consumable.deactivated` | Machine type consumable switched off | Reviewed fields only |
| `machine_type_consumable.deleted` | Consumable removed from a machine type | Reviewed fields only |
| `machine_type_consumable.updated` | Machine type consumable changed | Reviewed fields only |
| `machine_type_document.added` | Machine type document added | Reviewed fields only |
| `machine_type_document.removed` | Machine type document removed | Reviewed fields only |
| `machine_type_pricing.set` | Machine type pricing set | Withheld |
| `machine_type_pricing.updated` | Machine type pricing updated | Withheld |
| `machine_type_setup.booking_defaults_applied` | Machine type booking defaults applied to its spaces | Reviewed fields only |
| `machine_type_setup.updated` | Machine type setup changed | Reviewed fields only |
| `machine_type_template.deleted` | Machine type template deleted | Reviewed fields only |
| `machine_type_template.saved` | Machine type template saved | Reviewed fields only |
| `maintenance.document_added` | Maintenance document added | Reviewed fields only |
| `maintenance.document_deleted` | Maintenance document deleted | Reviewed fields only |
| `maintenance.feed_revoked` | Maintenance feed revoked | None declared |
| `maintenance.feed_rotated` | Maintenance feed rotated | None declared |
| `maintenance.logged` | Maintenance logged | Withheld |
| `maintenance.schedule_completed` | Maintenance schedule completed | Reviewed fields only |
| `maintenance.schedule_created` | Maintenance schedule created | Reviewed fields only |
| `maintenance.schedule_deactivated` | Maintenance schedule deactivated | Reviewed fields only |
| `maintenance.schedule_updated` | Maintenance schedule updated | Reviewed fields only |
| `maintenance.subject_logged` | Item or room maintenance logged | Reviewed fields only |
| `maintenance.subject_schedule_created` | Item or room maintenance scheduled | Withheld |
| `maintenance.subject_schedule_updated` | Item or room maintenance schedule changed | Reviewed fields only |
| `makerspace.archive_request_approved` | Makerspace archive request approved | Reviewed fields only |
| `makerspace.archive_request_declined` | Makerspace archive request declined | Reviewed fields only |
| `makerspace.archive_request_withdrawn` | Makerspace archive request withdrawn | Reviewed fields only |
| `makerspace.archive_requested` | Makerspace archive requested | Reviewed fields only |
| `makerspace.archived` | Makerspace archived | Withheld |
| `makerspace.capabilities_changed` | Makerspace capabilities changed | Withheld |
| `makerspace.capability_purge_started` | Capability data purge started | Reviewed fields only |
| `makerspace.capability_purged` | Capability data purged | Reviewed fields only |
| `makerspace.capability_retired` | Retired setting removed | Reviewed fields only |
| `makerspace.closed_notice_updated` | Closed-for-now banner updated | Reviewed fields only |
| `makerspace.community_policy_updated` | Community policy changed | Reviewed fields only |
| `makerspace.created` | Makerspace created | None declared |
| `makerspace.default_locale_changed` | Makerspace default language changed | Reviewed fields only |
| `makerspace.domain_changed` | Makerspace domain changed | None declared |
| `makerspace.domain_verify_attempt` | Makerspace domain verify attempt | Reviewed fields only |
| `makerspace.features_changed` | Makerspace features changed | None declared |
| `makerspace.features_updated` | Makerspace features updated | None declared |
| `makerspace.financial_year_updated` | Financial year start month changed | Reviewed fields only |
| `makerspace.geofence_updated` | Makerspace geofence updated | Withheld |
| `makerspace.guest_pass_policy_updated` | Guest pass policy changed | Reviewed fields only |
| `makerspace.module_purge_started` | Makerspace module purge started | Withheld |
| `makerspace.module_purged` | Makerspace module purged | Withheld |
| `makerspace.module_retired` | Retired module key folded into capabilities | Reviewed fields only |
| `makerspace.notification_recipients_updated` | Makerspace notification recipients updated | None declared |
| `makerspace.pack_configuration_updated` | Makerspace pack configuration updated | None declared |
| `makerspace.profile_updated` | Makerspace profile updated | None declared |
| `makerspace.public_api_key_rotated` | Public site browser key rotated | Reviewed fields only |
| `makerspace.publication_changed` | Makerspace publication changed | None declared |
| `makerspace.purge_started` | Makerspace purge started | Withheld |
| `makerspace.purged` | Makerspace purged | Withheld |
| `makerspace.return_policy_updated` | Makerspace return policy updated | Reviewed fields only |
| `makerspace.security_setting_changed` | Security setting changed | Reviewed fields only |
| `makerspace.security_setting_locked` | Security setting locked by the platform | Reviewed fields only |
| `makerspace.security_setting_unlocked` | Security setting unlocked by the platform | Reviewed fields only |
| `makerspace.space_pack_applied` | Makerspace space pack applied | None declared |
| `makerspace.subdomain_provisioned` | Makerspace subdomain provisioned | None declared |
| `makerspace.subdomain_request_approved` | Makerspace subdomain request approved | None declared |
| `makerspace.subdomain_request_rejected` | Makerspace subdomain request rejected | None declared |
| `makerspace.subdomain_requested` | Makerspace subdomain requested | None declared |
| `makerspace.unarchived` | Makerspace unarchived | None declared |
| `makerspace.updated` | Makerspace updated | None declared |
| `makerspace.waiver_deactivated` | Makerspace waiver deactivated | None declared |
| `makerspace.waiver_published` | Makerspace waiver published | Reviewed fields only |
| `makerspace.website_origins_updated` | Website embed origins updated | Reviewed fields only |
| `managed_hosting.billing_settings_updated` | Hosting billing settings changed | Reviewed fields only |
| `managed_hosting.hosting_switch_changed` | Hosting other makerspaces switched | Reviewed fields only |
| `managed_hosting.hosting_type_changed` | Hosting type changed (own or hosted space) | Reviewed fields only |
| `managed_hosting.invoice_checkout_started` | Hosting invoice checkout opened | Reviewed fields only |
| `managed_hosting.invoice_created` | Hosting invoice recorded | Reviewed fields only |
| `managed_hosting.invoice_paid` | Hosting invoice paid | Reviewed fields only |
| `managed_hosting.invoice_voided` | Hosting invoice voided | None declared |
| `managed_hosting.limit_defaults_changed` | Platform default limits changed | Reviewed fields only |
| `managed_hosting.limit_threshold_crossed` | Limit warning sent | Reviewed fields only |
| `managed_hosting.plan_assigned` | Hosting plan assigned | Reviewed fields only |
| `managed_hosting.plan_created` | Hosting plan created | Reviewed fields only |
| `managed_hosting.plan_removed` | Hosting plan removed | None declared |
| `managed_hosting.plan_updated` | Hosting plan changed | Reviewed fields only |
| `managed_hosting.throttle_rate_changed` | Request rate limit changed | Reviewed fields only |
| `managed_hosting.trial_expired` | Hosting trial ended | Reviewed fields only |
| `member.claim_code_issued` | Member claim code issued | Withheld |
| `member.claim_code_revoked` | Member claim code revoked | Withheld |
| `member.email_verification_failed` | Member email verification failed | Withheld |
| `member.email_verification_refused_walk_in` | Member email verification refused walk in | Withheld |
| `member.email_verification_requested` | Member email verification requested | Withheld |
| `member.email_verified` | Member email verified | Withheld |
| `member.phone_link_failed` | Member phone link failed | Withheld |
| `member.phone_link_refused_anonymous_requester` | Member phone link refused anonymous requester | Withheld |
| `member.phone_link_refused_walk_in` | Member phone link refused walk in | Withheld |
| `member.phone_link_requested` | Member phone link requested | Withheld |
| `member.phone_unlinked` | Member phone unlinked | Withheld |
| `member.phone_verified` | Member phone verified | Withheld |
| `member.profile_achievement_created` | Self-reported achievement added | Reviewed fields only |
| `member.profile_achievement_deleted` | Self-reported achievement deleted | None declared |
| `member.profile_achievement_updated` | Self-reported achievement updated | Reviewed fields only |
| `member.profile_image_cleared` | Member profile image cleared | Withheld |
| `member.profile_image_updated` | Member profile image updated | Withheld |
| `member.profile_opened` | Member profile created (open by default) | None declared |
| `member.profile_project_imported` | Hackathon submission imported as a project | None declared |
| `member.profile_timeline_created` | Profile timeline entry added | Reviewed fields only |
| `member.profile_timeline_deleted` | Profile timeline entry deleted | None declared |
| `member.profile_timeline_updated` | Profile timeline entry updated | Reviewed fields only |
| `member.profile_updated` | Member profile updated | Reviewed fields only |
| `member.public_handle_claimed` | Public profile handle claimed | Reviewed fields only |
| `member.public_handle_released` | Public profile handle released | None declared |
| `member.signup_expired` | Member signup expired | Withheld |
| `member.signup_requested` | Member signup requested | Withheld |
| `member.walk_in_application_created` | Member walk in application created | None declared |
| `member.walk_in_created` | Member walk in created | Reviewed fields only |
| `member.walk_in_guest_pass_created` | Walk-in registered with a guest pass | Reviewed fields only |
| `member.walk_in_transitioned` | Member walk in transitioned | None declared |
| `member_card.auto_issued` | Member card issued automatically | Reviewed fields only |
| `member_card.created` | Member card created | Reviewed fields only |
| `member_card.downloaded` | Member card downloaded | Reviewed fields only |
| `member_card.emailed` | Member card emailed | Reviewed fields only |
| `member_card.issued` | Member card issued | Reviewed fields only |
| `member_card.name_updated` | Member card name updated | Reviewed fields only |
| `member_card.photo_removed` | Member card photo removed | Reviewed fields only |
| `member_card.photo_updated` | Member card photo updated | Reviewed fields only |
| `member_card.printed` | Member card printed | Reviewed fields only |
| `member_card.reissued` | Member card reissued | Reviewed fields only |
| `member_card.revoked` | Member card revoked | Reviewed fields only |
| `member_card.scanned` | Member card scanned | Reviewed fields only |
| `member_card.settings_updated` | Member card settings changed | None declared |
| `member_card.template_updated` | Member card template updated | Reviewed fields only |
| `membership.admission_settings_updated` | Membership admission settings updated | None declared |
| `membership.adopted_from_import` | Membership adopted from import | Withheld |
| `membership.application_approved` | Membership application approved | None declared |
| `membership.application_exported` | Membership application exported | None declared |
| `membership.approved` | Membership approved | Withheld |
| `membership.bulk_decided` | Join requests decided in bulk | Reviewed fields only |
| `membership.consent_given` | Consent given | Reviewed fields only |
| `membership.consent_withdrawn` | Consent withdrawn | Reviewed fields only |
| `membership.day_pass_product_archived` | Day pass product archived | None declared |
| `membership.day_pass_product_saved` | Day pass product saved | Reviewed fields only |
| `membership.direct_admission` | Membership direct admission | None declared |
| `membership.erasure_approved` | Erasure approved | Reviewed fields only |
| `membership.erasure_rejected` | Erasure rejected | Reviewed fields only |
| `membership.erasure_requested` | Erasure requested | Reviewed fields only |
| `membership.erasure_withdrawn` | Erasure request withdrawn | Reviewed fields only |
| `membership.extended` | Membership extended by staff | Reviewed fields only |
| `membership.grace_promised` | Membership grace boundary recorded | None declared |
| `membership.guardian_consent_revoked` | Guardian consent revoked | None declared |
| `membership.guardian_consent_signed` | Guardian consent signed | Reviewed fields only |
| `membership.guardian_terms_published` | Guardian consent text published | Reviewed fields only |
| `membership.guest_pass_charge_raised` | Day pass charge raised | Reviewed fields only |
| `membership.guest_pass_charge_redirected` | Loan charge billed to a guest's sponsor | Reviewed fields only |
| `membership.guest_pass_converted` | Guest pass converted to a membership | Reviewed fields only |
| `membership.guest_pass_expired` | Guest pass expired | None declared |
| `membership.guest_pass_issued` | Guest pass issued | Reviewed fields only |
| `membership.guest_pass_kept_on_cancel` | Event pass kept after the registration was cancelled | Reviewed fields only |
| `membership.guest_pass_revoked` | Guest pass revoked | Reviewed fields only |
| `membership.guest_pass_waiver_stamped` | Guest pass waiver accepted | Reviewed fields only |
| `membership.import_accepted` | Imported membership accepted | Reviewed fields only |
| `membership.imported` | Members imported | Reviewed fields only |
| `membership.invitation_claimed` | Membership invitation claimed | None declared |
| `membership.invite_link_created` | Membership invite link created | Reviewed fields only |
| `membership.invite_link_redeemed` | Membership invite link used | Reviewed fields only |
| `membership.invite_link_revoked` | Membership invite link revoked | Reviewed fields only |
| `membership.invited` | Membership invited | Reviewed fields only |
| `membership.joined` | Membership joined | Withheld |
| `membership.left` | Member left makerspace | Withheld |
| `membership.minor_cleared` | Minor record cleared | None declared |
| `membership.minor_recorded` | Minor recorded | Reviewed fields only |
| `membership.payment_after_expiry` | Membership payment after expiry | None declared |
| `membership.plan_archived` | Membership plan archived | Reviewed fields only |
| `membership.plan_restored` | Membership plan restored | Reviewed fields only |
| `membership.record_updated` | Member record updated | Reviewed fields only |
| `membership.referred` | Membership referred | Reviewed fields only |
| `membership.renewal_cancelled` | Membership renewal cancelled | None declared |
| `membership.renewal_checkout_attempted` | Membership renewal checkout attempted | Reviewed fields only |
| `membership.renewal_raised` | Membership renewal raised | Reviewed fields only |
| `membership.renewal_reminder_sent` | Renewal reminder sent | Reviewed fields only |
| `membership.renewal_retry` | Membership renewal retry | Reviewed fields only |
| `membership.renewed` | Membership renewed | Reviewed fields only |
| `membership.request_activated` | Membership request activated | None declared |
| `membership.requested` | Membership requested | Withheld |
| `membership.revoked` | Membership revoked | Withheld |
| `membership.role_changed` | Membership role changed | Reviewed fields only |
| `membership.summary_opted_in` | Opted back in to the monthly membership summary | Reviewed fields only |
| `membership.summary_opted_out` | Opted out of the monthly membership summary | Reviewed fields only |
| `membership.term_cancelled` | Membership term cancelled | Reviewed fields only |
| `membership.term_charge_raised` | Membership term charge raised | Reviewed fields only |
| `membership.term_created` | Membership term created | Reviewed fields only |
| `membership.term_expired` | Membership term expired | Reviewed fields only |
| `membership.term_status_changed` | Membership term standing changed | Reviewed fields only |
| `membership.title_archived` | Member title archived | Reviewed fields only |
| `membership.title_assigned` | Member title assigned | Reviewed fields only |
| `membership.title_created` | Member title created | Reviewed fields only |
| `membership.title_restored` | Member title restored | Reviewed fields only |
| `membership.title_unassigned` | Member title removed | Reviewed fields only |
| `membership.title_updated` | Member title updated | Reviewed fields only |
| `membership.unverified` | Membership unverified | None declared |
| `membership.verified` | Membership verified | None declared |
| `membership.volunteer_credit_applied` | Volunteer credit applied to a charge | Reviewed fields only |
| `membership.volunteer_credit_created` | Volunteer credit earned | Reviewed fields only |
| `membership.volunteer_credit_voided` | Volunteer credit voided | None declared |
| `membership.volunteer_hours_decided` | Volunteer hours decided | Reviewed fields only |
| `membership.volunteer_hours_imported` | Event shift hours imported | Reviewed fields only |
| `membership.volunteer_hours_logged` | Volunteer hours logged | Reviewed fields only |
| `membership.vouched` | Membership vouched | None declared |
| `membership.vouchers_flagged` | Membership vouchers flagged | None declared |
| `membership.waiver_accepted` | Membership waiver accepted | Reviewed fields only |
| `membership.waiver_witnessed` | Membership waiver witnessed | Reviewed fields only |
| `membership_plan.created` | Membership plan created | Reviewed fields only |
| `membership_plan.updated` | Membership plan updated | Reviewed fields only |
| `mentor.help_alert_routed` | Mentor help alert posted to a chat room | Reviewed fields only |
| `mentor.help_alert_routes_changed` | Mentor help alert rooms changed | Reviewed fields only |
| `messaging.alias_correlated` | Messaging recipient alias correlated | None declared |
| `messaging.consent_archived` | Messaging consent archived | None declared |
| `messaging.consent_recorded` | Messaging consent recorded | None declared |
| `messaging.correlation_reset` | Messaging correlation reset | None declared |
| `messaging.correlations_blocked` | Messaging correlations blocked | None declared |
| `messaging.probe_claimed` | Messaging delivery probe claimed | None declared |
| `messaging.probe_confirmed` | Messaging delivery probe confirmed | None declared |
| `messaging.probe_released` | Messaging delivery probe released | None declared |
| `messaging.recipient_suppressed` | Messaging recipient suppressed | None declared |
| `messaging.retired_credentials_wiped` | Retired messaging credentials wiped | None declared |
| `messaging.test_enqueued` | Messaging test queued | None declared |
| `native_app.registration_updated` | Mobile app identity saved | Reviewed fields only |
| `native_app.revoked` | Native app revoked | Reviewed fields only |
| `notification.account_scrubbed` | Personal notification history scrubbed | None declared |
| `notification.broadcast_created` | Notification broadcast created | None declared |
| `notification.browser_alert_subscribed` | Browser notifications switched on | None declared |
| `notification.browser_alert_unsubscribed` | Browser notifications switched off | None declared |
| `notification.browser_firebase_challenge_started` | Browser notification sign-up started | None declared |
| `notification.browser_firebase_subscribed` | Browser notifications turned on | None declared |
| `notification.browser_firebase_unsubscribed` | Browser notifications turned off | None declared |
| `notification.channel_configured` | Notification channel configured | Reviewed fields only |
| `notification.channel_preferences_updated` | Personal notification channels updated | Reviewed fields only |
| `notification.channel_tested` | Notification channel tested | Reviewed fields only |
| `notification.chat_install_started` | Chat installation started | Reviewed fields only |
| `notification.chat_install_state_consumed` | Chat installation proof consumed | Reviewed fields only |
| `notification.delivery_observed` | Notification delivery status observed | None declared |
| `notification.delivery_requeued` | Notification delivery requeued | Reviewed fields only |
| `notification.destination_auto_disabled` | Chat room switched off after failed deliveries | Reviewed fields only |
| `notification.destination_created` | Notification destination created | Reviewed fields only |
| `notification.destination_deleted` | Notification destination deleted | Reviewed fields only |
| `notification.destination_updated` | Notification destination updated | Reviewed fields only |
| `notification.email_accepted` | Notification email accepted | None declared |
| `notification.endpoint_challenge_started` | Notification account link started | Reviewed fields only |
| `notification.endpoint_revoked` | Notification account disconnected | Reviewed fields only |
| `notification.endpoint_verified` | Notification account linked | Reviewed fields only |
| `notification.escalated` | Unseen staff notice escalated | Reviewed fields only |
| `notification.inbox_archived` | Personal notification archived | None declared |
| `notification.inbox_read` | Personal notification read | None declared |
| `notification.inbox_read_all` | Personal notifications marked read | Reviewed fields only |
| `notification.inbox_restored` | Personal notification restored | None declared |
| `notification.inbox_snoozed` | Personal notification snoozed | None declared |
| `notification.media_grant_cleaned` | Document delivery grant cleaned up | Reviewed fields only |
| `notification.media_grant_consumed` | Document delivery grant consumed | Reviewed fields only |
| `notification.media_grant_issued` | Document delivery grant issued | Reviewed fields only |
| `notification.preference_updated` | Personal notification preference updated | Withheld |
| `notification.preferences_updated` | Notification preferences updated | None declared |
| `notification.read` | Notification marked read | None declared |
| `notification.read_all` | All notifications marked read | Reviewed fields only |
| `notification.recipients_selected` | Notification recipients selected | Withheld |
| `notification.test_sent` | Notification delivery test sent | None declared |
| `notification.timing_updated` | Notification timing updated | None declared |
| `notification.unsubscribed` | Personal notification emails unsubscribed | Withheld |
| `notification.webhook_received` | Notification provider receipt recorded | None declared |
| `notification.whatsapp_delivery_updated` | WhatsApp delivery updated | Reviewed fields only |
| `notification.whatsapp_templates_refreshed` | WhatsApp template approvals refreshed | Reviewed fields only |
| `oauth_app.created` | App registered | Reviewed fields only |
| `oauth_app.deleted` | App deleted | None declared |
| `oauth_app.updated` | App changed | Reviewed fields only |
| `oauth_consent.granted` | App connected | Reviewed fields only |
| `oauth_consent.revoked` | App disconnected | None declared |
| `organization.created` | Organization created | Withheld |
| `organization.deleted` | Organization deleted | Reviewed fields only |
| `organization.email_sender_updated` | Organisation event-email sender updated | Reviewed fields only |
| `organization.hours_adjusted` | Organization hours granted or adjusted | Reviewed fields only |
| `organization.hours_allowance_updated` | Organization hours allowance changed | Reviewed fields only |
| `organization.invitation_created` | Organization invitation created | Reviewed fields only |
| `organization.invitation_delivered` | Organisation invitation sent by email/chat | Reviewed fields only |
| `organization.invitation_redeemed` | Organization invitation redeemed | Reviewed fields only |
| `organization.invitation_revoked` | Organization invitation revoked | Reviewed fields only |
| `organization.link_created` | Organization link created | Withheld |
| `organization.link_deleted` | Organization link deleted | None declared |
| `organization.link_updated` | Organization link updated | Withheld |
| `organization.member_departed` | Organization member departed | Reviewed fields only |
| `organization.member_left` | Organization member left | None declared |
| `organization.membership_created` | Organization membership created | Withheld |
| `organization.membership_deleted` | Organization membership deleted | Reviewed fields only |
| `organization.membership_updated` | Organization membership updated | Withheld |
| `organization.profile_updated` | Organization profile updated | Reviewed fields only |
| `organization.self_created` | Organization created by its owner | None declared |
| `organization.updated` | Organization updated | Withheld |
| `payment.billing_policy_updated` | Payment billing policy updated | None declared |
| `payment.canceled` | Payment canceled | None declared |
| `payment.capture_flag_resolved` | Unexpected online payment decided | Reviewed fields only |
| `payment.capture_flagged` | Unexpected online payment flagged | Reviewed fields only |
| `payment.checkout_abandoned` | Unpaid online checkout closed after a week | Reviewed fields only |
| `payment.checkout_created` | Payment checkout created | Reviewed fields only |
| `payment.checkout_expired` | Payment checkout expired | Reviewed fields only |
| `payment.created` | Payment created | Reviewed fields only |
| `payment.dispute_opened` | Payment dispute opened | Reviewed fields only |
| `payment.dispute_updated` | Payment dispute updated | Reviewed fields only |
| `payment.document_held` | Receipt held for a staff decision | Reviewed fields only |
| `payment.document_issued` | Payment document issued | None declared |
| `payment.document_released` | Held receipt released | Reviewed fields only |
| `payment.double_paid_refund_required` | Payment double paid refund required | Reviewed fields only |
| `payment.event_money_settings_updated` | Prize tax and payee settings changed | None declared |
| `payment.failed` | Payment failed | None declared |
| `payment.manual_reminder_sent` | Payment reminder sent | Reviewed fields only |
| `payment.mobile_intent_created` | Payment mobile intent created | Reviewed fields only |
| `payment.mobile_order_created` | Mobile payment order created | None declared |
| `payment.paid_after_terminal` | Payment paid after terminal | Reviewed fields only |
| `payment.paid_claim_confirmed` | Offline payment claim confirmed | Reviewed fields only |
| `payment.paid_claim_rejected` | Offline payment claim rejected | Reviewed fields only |
| `payment.paid_claim_submitted` | Offline payment claim submitted | Reviewed fields only |
| `payment.paid_claim_superseded` | Offline payment claim closed: charge settled another way | Reviewed fields only |
| `payment.paid_offline` | Payment paid offline | Withheld |
| `payment.paid_online` | Payment paid online | Reviewed fields only |
| `payment.pay_link_created` | Pay link created | Reviewed fields only |
| `payment.pay_link_used` | Pay link opened | Reviewed fields only |
| `payment.refund_amended` | Payment refund amended | None declared |
| `payment.refund_case_term_ended` | Refund approval ended the membership term | Withheld |
| `payment.refund_failed` | Payment refund failed | Withheld |
| `payment.refund_pending_flagged` | Provider refund still pending after a day | Reviewed fields only |
| `payment.refund_policy_updated` | Payment refund policy updated | Reviewed fields only |
| `payment.refund_recorded` | Payment refund recorded | None declared |
| `payment.refund_requested` | Payment refund requested | Reviewed fields only |
| `payment.refunded` | Payment refunded | Withheld |
| `payment.settlement_amended` | Payment settlement amended | Reviewed fields only |
| `payment.settlement_awaiting_confirmation` | Offline settlement awaiting a second person | Reviewed fields only |
| `payment.settlement_confirmed` | Offline settlement confirmed by a second person | Reviewed fields only |
| `payment.settlement_rejected` | Offline settlement rejected by the second person | Reviewed fields only |
| `payment.settlement_superseded` | Offline settlement proposal closed: charge settled another way | Reviewed fields only |
| `payment.tax_settings_updated` | Tax settings updated | Reviewed fields only |
| `payment.waived` | Payment waived | Withheld |
| `payments.connect_account_mapped` | Payments connect account mapped | Withheld |
| `payments.connect_authorization_revoked` | Payments connect authorization revoked | Withheld |
| `payments.connect_callback_consumed` | Payments connect callback consumed | Withheld |
| `payments.connect_deauthorization_ignored` | Payments connect deauthorization ignored | Withheld |
| `payments.connect_deauthorized` | Payments connect deauthorized | Withheld |
| `payments.connect_onboarded` | Payments connect onboarded | Withheld |
| `payments.connect_onboarding_started` | Payments connect onboarding started | Withheld |
| `payments.connect_previous_authorization_revoked` | Payments connect previous authorization revoked | Withheld |
| `payments.connect_status_update_ignored` | Payments connect status update ignored | Withheld |
| `payments.connect_status_updated` | Payments connect status updated | Withheld |
| `payments.settings_updated` | Payments settings updated | None declared |
| `perk.copied` | Tier perks copied to a sponsor | Reviewed fields only |
| `perk.created` | Sponsor perk added | Reviewed fields only |
| `perk.fulfilled` | Sponsor perk fulfilled | Reviewed fields only |
| `perk.reopened` | Sponsor perk reopened | Reviewed fields only |
| `perk.updated` | Sponsor perk changed | Reviewed fields only |
| `platform.admins_viewed` | Platform admin list viewed | Reviewed fields only |
| `platform.attestation_settings_updated` | App attestation settings changed | Reviewed fields only |
| `platform.email_settings_updated` | Platform email settings updated | None declared |
| `platform.firebase_web_settings_updated` | Platform Firebase web settings changed | Reviewed fields only |
| `platform.inbox_viewed` | Cross-space inbox viewed | Reviewed fields only |
| `platform.ip_rule_deleted` | Platform IP rule deleted | Reviewed fields only |
| `platform.ip_rule_saved` | Platform IP rule saved | Reviewed fields only |
| `platform.login_methods_updated` | Sign-in methods changed | Reviewed fields only |
| `platform.oidc_provider_saved` | Single sign-on provider saved | Reviewed fields only |
| `platform.overview_exported` | Platform overview exported | Reviewed fields only |
| `platform.pii_access_closed` | Platform PII access closed | Reviewed fields only |
| `platform.pii_access_opened` | Platform PII access opened | Reviewed fields only |
| `platform.provider_test` | Platform provider credentials tested | Reviewed fields only |
| `platform.push_settings_updated` | Platform push settings changed | Reviewed fields only |
| `platform.searched` | Platform search run | Reviewed fields only |
| `platform.sms_settings_updated` | Platform SMS settings changed | Reviewed fields only |
| `platform.social_auth_settings_updated` | Platform social auth settings updated | Reviewed fields only |
| `platform.space_pack_profile_saved` | Platform space pack profile saved | None declared |
| `platform.stripe_connect_settings_updated` | Platform stripe connect settings updated | Reviewed fields only |
| `platform.whatsapp_settings_updated` | Platform WhatsApp settings changed | Reviewed fields only |
| `platform.whatsapp_template_updated` | Platform whatsapp template updated | Withheld |
| `platform_credential_limit.reached` | Platform credential allowance reached | Reviewed fields only |
| `pledge.cancelled` | Donation pledge cancelled | Reviewed fields only |
| `pledge.created` | Donation pledge made | Reviewed fields only |
| `pledge.paused` | Donation pledge paused | Reviewed fields only |
| `pledge.period_raised` | Pledge period charge raised | Reviewed fields only |
| `pledge.resumed` | Donation pledge resumed | Reviewed fields only |
| `pledge.updated` | Donation pledge changed | Reviewed fields only |
| `presence.display_claimed` | Space display screen paired | Reviewed fields only |
| `presence.display_unpaired` | Space display screen unpaired | None declared |
| `presence.display_updated` | Space display screen changed | Reviewed fields only |
| `presence.ended` | Presence ended | None declared |
| `presence.ended_claim_revoked` | Presence ended claim revoked | Reviewed fields only |
| `presence.ended_membership_revoked` | Presence ended membership revoked | None declared |
| `presence.expired` | Presence expired | Reviewed fields only |
| `presence.expiry_reminded` | Presence expiry reminder queued | None declared |
| `presence.expiry_reminder_skipped` | Stale presence reminder skipped | None declared |
| `presence.preference_updated` | Presence display preference changed | None declared |
| `presence.renewed` | Presence renewed | None declared |
| `presence.settings_updated` | Presence display settings changed | None declared |
| `presence.started` | Presence started | None declared |
| `pricing.discount_archived` | Member discount archived | Reviewed fields only |
| `pricing.discount_created` | Member discount created | Reviewed fields only |
| `pricing.discount_updated` | Member discount changed | Reviewed fields only |
| `pricing.override_cleared` | Item price set back to the default | Reviewed fields only |
| `pricing.override_set` | Item price set | Reviewed fields only |
| `pricing.price_drop_refunds_opened` | Refund cases opened after a price drop | Reviewed fields only |
| `problem_report.triaged` | Problem report triaged | Reviewed fields only |
| `procurement.auto_tobuy_created` | Automatic To-Buy created | Reviewed fields only |
| `procurement.bought` | To-Buy item marked bought | Reviewed fields only |
| `procurement.consumable_refilled` | Machine consumable refilled from To-Buy | Reviewed fields only |
| `procurement.item_added` | Procurement item added | None declared |
| `procurement.item_removed` | Procurement item removed | None declared |
| `procurement.item_updated` | Procurement item updated | None declared |
| `procurement.low_stock_flagged` | Procurement low stock flagged | Reviewed fields only |
| `procurement.moved_to_inventory` | Procurement moved to inventory | Reviewed fields only |
| `procurement.moved_to_printing` | Procurement moved to printing | Reviewed fields only |
| `procurement.receipt_added` | Procurement receipt added | None declared |
| `procurement.receipt_removed` | Procurement receipt removed | None declared |
| `public_page.asset_bytes_deleted` | Public page image storage released | Reviewed fields only |
| `public_page.asset_deleted` | Public page image deleted | Withheld |
| `public_page.asset_reserved` | Public page image upload reserved | Withheld |
| `public_page.asset_uploaded` | Public page image uploaded | Withheld |
| `public_page.handle_claimed` | Public page handle claimed | Withheld |
| `public_page.handle_released` | Public page handle released | Withheld |
| `public_page.published` | Public page published | Withheld |
| `public_page.unattached_assets_removed` | Unattached public page images removed | Reviewed fields only |
| `public_page.unpublished` | Public page unpublished | Withheld |
| `public_page.updated` | Public page draft saved | Withheld |
| `public_problem.resolved` | Public problem resolved | Reviewed fields only |
| `public_tool.checked_out` | Public tool checked out | Reviewed fields only |
| `public_tool.problem_reported` | Public tool problem reported | Reviewed fields only |
| `public_tool.returned` | Public tool returned | Reviewed fields only |
| `push.device_deleted` | Push device deleted | Reviewed fields only |
| `push.device_registered` | Push device registered | Reviewed fields only |
| `qr.asset_created` | Asset QR code created | None declared |
| `qr.box_created` | Qr box created | None declared |
| `qr.external_assigned` | External QR code linked | Reviewed fields only |
| `qr.rebound` | Qr rebound | Withheld |
| `qr.revoked` | Qr revoked | None declared |
| `qr.scanned` | Qr scanned | Reviewed fields only |
| `qr.tool_created` | Qr tool created | Withheld |
| `qr.tool_reused` | Qr tool reused | Withheld |
| `qr_print_batch.created` | Qr print batch created | None declared |
| `qr_print_batch.item_saved` | Qr print batch item saved | None declared |
| `qr_print_batch.items_saved` | Qr print batch items saved | None declared |
| `qr_print_batch.printed` | Qr print batch printed | None declared |
| `report.downloaded` | Report downloaded | None declared |
| `report.previewed` | Report previewed | None declared |
| `report.retention_fence_satisfied` | Report retention fence satisfied | Reviewed fields only |
| `report.rollup_backfill_completed` | Report rollup backfill completed | Reviewed fields only |
| `report.rollup_finalized` | Report rollup finalized | Reviewed fields only |
| `report.rollup_revision_appended` | Report rollup revision appended | Reviewed fields only |
| `report_schedule.created` | Report schedule created | Reviewed fields only |
| `report_schedule.deleted` | Report schedule deleted | Reviewed fields only |
| `report_schedule.delivered` | Report schedule delivered | Withheld |
| `report_schedule.failed` | Report schedule failed | Withheld |
| `report_schedule.recipients_pruned_by_migration` | Report schedule recipients pruned by role migration | None declared |
| `report_schedule.skipped` | Report schedule skipped | Reviewed fields only |
| `report_schedule.updated` | Report schedule updated | Reviewed fields only |
| `request.accepted` | Request accepted | Reviewed fields only |
| `request.cancelled` | Request withdrawn | Reviewed fields only |
| `request.contact_code_failed` | Borrower email code refused | None declared |
| `request.contact_code_sent` | Borrower email code sent | None declared |
| `request.expired` | Request expired uncollected | Reviewed fields only |
| `request.issued` | Request issued | Reviewed fields only |
| `request.rejected` | Request rejected | None declared |
| `request.renewed` | Loan renewed | Reviewed fields only |
| `request.return_due_updated` | Request return due updated | Reviewed fields only |
| `request.submitted` | Request submitted | None declared |
| `rls.capability_used` | Cross-space capability used | Reviewed fields only |
| `rls.report_only_violation` | Cross-space row reported (RLS report-only) | Reviewed fields only |
| `saved_view.created` | Saved view created | None declared |
| `saved_view.deleted` | Saved view deleted | None declared |
| `saved_view.shared` | Saved view shared | Withheld |
| `saved_view.unshared` | Saved view made private | Withheld |
| `saved_view.updated` | Saved view updated | None declared |
| `selfhost_move.approved` | Move to own server approved | Reviewed fields only |
| `selfhost_move.artifact_discarded` | Move export file deleted | Reviewed fields only |
| `selfhost_move.downloaded` | Move export downloaded | Reviewed fields only |
| `selfhost_move.export_failed` | Move export failed | Reviewed fields only |
| `selfhost_move.export_started` | Move export started | Reviewed fields only |
| `selfhost_move.exported` | Move export finished | Reviewed fields only |
| `selfhost_move.imported` | Space imported from a move | Reviewed fields only |
| `selfhost_move.rejected` | Move to own server declined | Reviewed fields only |
| `selfhost_move.requested` | Move to own server requested | Reviewed fields only |
| `service_state.changed` | Service state changed | Withheld |
| `settings.changed` | Setting changed | Reviewed fields only |
| `settings.grant_created` | Settings grant created | Reviewed fields only |
| `settings.grant_revoked` | Settings grant revoked | Reviewed fields only |
| `settings.lock_created` | Setting locked | Reviewed fields only |
| `settings.lock_released` | Setting lock released | Reviewed fields only |
| `shop.cash_session_close_proposed` | Cash-up waiting for a second check | None declared |
| `shop.cash_session_closed` | Cash-up closed | None declared |
| `shop.cash_session_opened` | Cash drawer opened | None declared |
| `shop.event_offers_set` | Shop items offered at an event changed | None declared |
| `shop.order_cancelled` | Shop order cancelled | None declared |
| `shop.order_collected` | Shop order collected | None declared |
| `shop.order_paid` | Shop order paid | None declared |
| `shop.order_paid_at_desk` | Shop order paid at the desk | None declared |
| `shop.order_pickup_moved_to_space` | Shop pickup moved to the makerspace | None declared |
| `shop.order_placed` | Shop order placed | None declared |
| `shop.order_ready` | Shop order ready for pickup | None declared |
| `shop.order_unfulfilled` | Paid shop order could not be filled | None declared |
| `shop.pos_sale` | Front-desk sale | None declared |
| `shop.product_archived` | Shop product archived | None declared |
| `shop.product_created` | Shop product created | None declared |
| `shop.product_image_cleared` | Shop product image removed | None declared |
| `shop.product_image_set` | Shop product image set | None declared |
| `shop.product_updated` | Shop product changed | None declared |
| `shop.receipt_emailed` | Shop receipt emailed | Reviewed fields only |
| `shop.refund_requested` | Shop refund opened | None declared |
| `shop.stock_adjusted` | Shop stock adjusted | None declared |
| `shop.stock_restocked` | Shop stock restocked | None declared |
| `shop.stock_returned` | Shop items returned to stock | None declared |
| `shop.stock_written_off` | Shop items written off | None declared |
| `shop.variant_archived` | Shop variant archived | None declared |
| `shop.variant_created` | Shop variant created | None declared |
| `shop.variant_updated` | Shop variant changed | None declared |
| `space_control.announcement_cancelled` | Platform announcement cancelled | None declared |
| `space_control.announcement_created` | Platform announcement created | Reviewed fields only |
| `space_control.announcement_emailed` | Platform announcement emailed | Reviewed fields only |
| `space_control.limits_changed` | Space limits changed | Reviewed fields only |
| `space_control.ownership_invited` | New Space Manager invited (ownership transfer) | Reviewed fields only |
| `space_control.ownership_transferred` | Space ownership transferred | Reviewed fields only |
| `space_control.read_only_enabled` | Space put in read-only mode | Reviewed fields only |
| `space_control.read_only_lifted` | Read-only mode ended | Reviewed fields only |
| `space_control.schedule_blocked` | Scheduled archive or purge held | Reviewed fields only |
| `space_control.schedule_cancelled` | Scheduled archive or purge cancelled | None declared |
| `space_control.schedule_cleared` | Scheduled purge cleared | Reviewed fields only |
| `space_control.schedule_set` | Archive and purge scheduled | Reviewed fields only |
| `space_control.scheduled_archive_ran` | Space archived as scheduled | Reviewed fields only |
| `space_control.scheduled_purge_ran` | Space purged as scheduled | Reviewed fields only |
| `space_control.space_onboarded` | Space created from a hosting request | Reviewed fields only |
| `space_control.superadmin_bypass` | Superadmin acted in a paused or read-only space | Reviewed fields only |
| `space_control.suspended` | Space paused by the platform operator | Reviewed fields only |
| `space_control.unsuspended` | Space unblocked by the platform operator | Reviewed fields only |
| `sponsor.archived` | Sponsor archived | Reviewed fields only |
| `sponsor.charge_paid` | Sponsorship payment received | Reviewed fields only |
| `sponsor.charge_raised` | Sponsorship payment recorded as owed | Reviewed fields only |
| `sponsor.created` | Sponsor added | Reviewed fields only |
| `sponsor.event_linked` | Sponsor linked to an event | Reviewed fields only |
| `sponsor.event_unlinked` | Sponsor unlinked from an event | Reviewed fields only |
| `sponsor.logo_removed` | Sponsor logo removed | Reviewed fields only |
| `sponsor.logo_updated` | Sponsor logo changed | Reviewed fields only |
| `sponsor.restored` | Sponsor restored | Reviewed fields only |
| `sponsor.tier_created` | Sponsor tier created | Reviewed fields only |
| `sponsor.tier_updated` | Sponsor tier changed | Reviewed fields only |
| `sponsor.updated` | Sponsor changed | Reviewed fields only |
| `staff.created` | Staff created | Withheld |
| `staff.invitation_revoked_by_migration` | Staff invitation revoked by role migration | None declared |
| `staff.machine_scope_changed` | Staff machine scope changed | None declared |
| `staff.membership_updated` | Staff membership updated | Withheld |
| `staff.roles_changed` | Staff roles changed | Reviewed fields only |
| `staff.roles_migrated` | Staff roles migrated to fixed catalogue | Reviewed fields only |
| `staff_invitation.accept_failed` | Staff invitation code rejected | None declared |
| `staff_invitation.accepted` | Staff invitation accepted | Reviewed fields only |
| `staff_invitation.revoked` | Staff invitation revoked | None declared |
| `staff_invitation.sent` | Staff invitation sent | Reviewed fields only |
| `staff_role.changed` | Staff role changed | Reviewed fields only |
| `staff_role.granted` | Staff role granted | Reviewed fields only |
| `staff_role.restored` | Staff role restored | Reviewed fields only |
| `staff_role.revoked` | Staff role revoked | Reviewed fields only |
| `station_credentials.revoked_on_restore` | Station credentials revoked after a restore | Reviewed fields only |
| `stock_transfer.applied` | Stock transfer applied | None declared |
| `stock_transfer.received` | Stock transfer received | Reviewed fields only |
| `stocktake.adjustments_applied` | Stocktake adjustments applied | None declared |
| `stocktake.approved` | Stocktake approved | None declared |
| `stocktake.completed` | Stocktake completed | None declared |
| `stocktake.created` | Stocktake created | None declared |
| `stocktake.line_counted` | Stocktake line counted | Reviewed fields only |
| `stocktake.policy_updated` | Stocktake policy updated | None declared |
| `stocktake.schedule_created` | Stocktake schedule created | None declared |
| `stocktake.schedule_deleted` | Stocktake schedule deleted | None declared |
| `stocktake.schedule_updated` | Stocktake schedule updated | None declared |
| `stocktake.scheduled` | Stocktake scheduled | None declared |
| `storage.bucket_binding_migrated` | Storage binding migrated | Reviewed fields only |
| `storage.bucket_handoff_resumed` | Storage handoff resumed | Reviewed fields only |
| `storage.capabilities_verification_failed` | Storage capabilities verification failed | None declared |
| `storage.capabilities_verified` | Storage capabilities verified | Withheld |
| `storage.legacy_receipt_bound` | Legacy storage receipt bound | Reviewed fields only |
| `storage.object_lock_probe_requested` | Storage object lock probe requested | None declared |
| `storage.reservations_reconciled` | Storage reservations reconciled | Reviewed fields only |
| `subject_export.download_url_issued` | Personal data export download issued | Reviewed fields only |
| `subject_export.failed` | Personal data export failed | Reviewed fields only |
| `subject_export.requested` | Personal data export requested | None declared |
| `subject_export.started` | Personal data export started | None declared |
| `technician.archived` | Technician archived | Reviewed fields only |
| `technician.consent_withdrawn` | Technician chat consent withdrawn | Reviewed fields only |
| `technician.created` | Technician added | Reviewed fields only |
| `technician.default_removed` | Default technician removed | Withheld |
| `technician.default_set` | Default technician set | Withheld |
| `technician.opt_in_link_created` | Technician opt-in link sent | Reviewed fields only |
| `technician.opted_in` | Technician opted in to chat | Reviewed fields only |
| `technician.updated` | Technician changed | Reviewed fields only |
| `telegram.test_sent` | Telegram test alert sent | None declared |
| `tenant_migration.api_client_reissued` | Tenant migration api client reissued | Reviewed fields only |
| `tenant_migration.deployment_identity_read` | Tenant migration deployment identity read | Reviewed fields only |
| `tenant_migration.disclosure_approvals_read` | Tenant migration disclosure approvals read | Reviewed fields only |
| `tenant_migration.disclosure_approved` | Tenant migration disclosure approved | Reviewed fields only |
| `tenant_migration.disclosure_computed` | Tenant migration disclosure computed | Reviewed fields only |
| `tenant_migration.disclosure_revoked` | Tenant migration disclosure revoked | Reviewed fields only |
| `tenant_migration.export_read` | Tenant migration export read | Reviewed fields only |
| `tenant_migration.export_requested` | Tenant migration export requested | Reviewed fields only |
| `tenant_migration.exports_read` | Tenant migration exports read | Reviewed fields only |
| `tenant_migration.identity_decisions_read` | Tenant migration identity decisions read | Reviewed fields only |
| `tenant_migration.identity_decisions_submitted` | Tenant migration identity decisions submitted | Reviewed fields only |
| `tenant_migration.import_completed` | Tenant migration import completed | Reviewed fields only |
| `tenant_migration.import_created` | Tenant migration import created | Reviewed fields only |
| `tenant_migration.import_read` | Tenant migration import read | Reviewed fields only |
| `tenant_migration.import_run_refused` | Tenant migration import run refused | Reviewed fields only |
| `tenant_migration.import_run_requested` | Tenant migration import run requested | Reviewed fields only |
| `tenant_migration.import_staging_failed` | Tenant migration import staging failed | Reviewed fields only |
| `tenant_migration.import_upload_chunk_received` | Tenant migration import upload chunk received | Reviewed fields only |
| `tenant_migration.import_upload_received` | Tenant migration import upload received | Reviewed fields only |
| `tenant_migration.import_upload_started` | Tenant migration import upload started | Reviewed fields only |
| `tenant_migration.imports_read` | Tenant migration imports read | Reviewed fields only |
| `tenant_migration.objects_promoted` | Tenant migration objects promoted | Reviewed fields only |
| `tenant_migration.objects_rolled_back` | Tenant migration objects rolled back | Reviewed fields only |
| `tenant_migration.objects_staged` | Tenant migration objects staged | Reviewed fields only |
| `tenant_migration.pairing_approved` | Tenant migration pairing approved | Reviewed fields only |
| `tenant_migration.pairings_read` | Tenant migration pairings read | Reviewed fields only |
| `tenant_migration.source_gate_capture_released` | Tenant migration source gate capture released | Withheld |
| `tenant_migration.source_gate_closed` | Tenant migration source gate closed | Withheld |
| `tenant_migration.source_gate_migrated_out` | Tenant migration source gate migrated out | Withheld |
| `tenant_migration.source_gate_recovery_command` | Tenant migration source gate recovery command | Withheld |
| `tenant_migration.source_migrated_out` | Tenant migration source migrated out | Reviewed fields only |
| `tenant_migration.source_quiesced` | Tenant migration source quiesced | Reviewed fields only |
| `tenant_migration.source_reopened` | Tenant migration source reopened | Reviewed fields only |
| `tenant_migration.staff_roles_granted` | Tenant migration staff roles granted to a linked person | Reviewed fields only |
| `tenant_migration.target_aborted` | Tenant migration target aborted | Reviewed fields only |
| `tenant_migration.target_activated` | Tenant migration target activated | Reviewed fields only |
| `tenant_migration.target_blind_indexes_rebuilt` | Tenant migration target blind indexes rebuilt | Reviewed fields only |
| `tenant_migration.target_deks_installed` | Tenant migration target deks installed | Reviewed fields only |
| `tenant_migration.target_encryption_ready` | Tenant migration target encryption ready | Reviewed fields only |
| `tenant_migration.target_search_generation_created` | Tenant migration target search generation created | Reviewed fields only |
| `tenant_migration.target_superadmin_created` | Tenant migration target superadmin created | Reviewed fields only |
| `tenant_migration.tenant_dump_artifact_cleanup_required` | Tenant migration tenant dump artifact cleanup required | None declared |
| `tenant_migration.tenant_dump_capture_failed` | Tenant migration tenant dump capture failed | None declared |
| `tenant_migration.tenant_dump_captured` | Tenant migration tenant dump captured | Reviewed fields only |
| `tenant_migration.tenant_dump_derivation_failed` | Tenant migration tenant dump derivation failed | None declared |
| `tenant_migration.tenant_dump_derived` | Tenant migration tenant dump derived | Reviewed fields only |
| `tenant_migration.tenant_dump_publication_refused` | Tenant migration tenant dump publication refused | Reviewed fields only |
| `tenant_migration.tenant_dump_published` | Tenant migration tenant dump published | Reviewed fields only |
| `tenant_migration.tenant_dump_requested` | Tenant migration tenant dump requested | Reviewed fields only |
| `tenant_migration.verification_read` | Tenant migration verification read | Reviewed fields only |
| `user.access_restored` | User access restored | None declared |
| `user.access_restricted` | User access restricted | Reviewed fields only |
| `user.password_changed` | User password changed | None declared |
| `user.password_reset` | User password reset | None declared |
| `user.password_reset_via_email` | User password reset via email | Reviewed fields only |
| `vendor.archived` | Vendor archived | Reviewed fields only |
| `vendor.created` | Vendor added | Reviewed fields only |
| `vendor.updated` | Vendor changed | Reviewed fields only |
| `wallet_pass.guest_issued` | Guest pass added to a wallet | Reviewed fields only |
| `wallet_pass.issued` | Wallet pass issued | Reviewed fields only |
| `wallet_pass.updated` | Wallet pass updated | Reviewed fields only |
| `wallet_pass.voided` | Wallet pass voided | Reviewed fields only |
| `warranty.created` | Warranty created | Withheld |
| `warranty.document_added` | Warranty document added | None declared |
| `warranty.document_removed` | Warranty document removed | None declared |
| `warranty.updated` | Warranty updated | Withheld |
| `work_order.assigned` | Work order assigned | Reviewed fields only |
| `work_order.cancelled` | Work order cancelled | Reviewed fields only |
| `work_order.closed` | Work order closed | Reviewed fields only |
| `work_order.created` | Work order opened | Reviewed fields only |
| `work_order.held` | Work order put on hold | Reviewed fields only |
| `work_order.started` | Work order started | Reviewed fields only |

## Actions emitted through shared services

The following prefixes cover reviewed shared-service audit actions. They can emit additional keys at runtime. Staff projections always withhold their metadata.

- `admin_direct.`
- `auth.`
- `booking.`
- `booking.broadcast.`
- `booking.staff_grant_`
- `booking.website_`
- `devices.`
- `dispatch.sent`
- `encryption.dek_`
- `event.`
- `event.broadcast.`
- `event.staff_grant_`
- `event.website_`
- `evidence.upload_url_issued`
- `inventory.asset_needs_fix_`
- `inventory.image_`
- `inventory.needs_fix_`
- `issue.assigned`
- `issue.closed`
- `issue.opened`
- `issue.rejected`
- `issue.reported`
- `issue.triaged`
- `issue.unassigned`
- `item.`
- `kiosk.evidence_upload_issued`
- `machine.`
- `machine_consumable_pool.`
- `machine_service.`
- `makerspace.cover_`
- `makerspace.logo_`
- `member.claim_code_`
- `membership.awaiting_payment`
- `membership.awaiting_vouches`
- `membership.can_`
- `membership.canceled`
- `membership.expired`
- `membership.requested`
- `membership.revoked`
- `membership.vouches_satisfied`
- `messaging.delivery_`
- `messaging.provider_status`
- `notification.cutover_`
- `payment.refund_case_`
- `payments.connect_`
- `public_page.asset_deleted`
- `public_page.asset_reserved`
- `public_page.asset_uploaded`
- `public_page.handle_claimed`
- `public_page.handle_released`
- `public_page.published`
- `public_page.unpublished`
- `public_page.updated`
- `repair.`
- `request.closed_with_issue`
- `request.partially_returned`
- `request.returned`
- `service_state.changed`
- `tenant_migration.source_gate_`
- `wallet_pass.credentials_`

An action outside the presentation catalogue and reviewed policy appears as “Unrecognized audit action” with its metadata withheld.
