# Events programme source map

GF4 authored integration, `lane/events-g2` (2026-10-18). Continued from [SOURCE-MAP.md](SOURCE-MAP.md).
Paths below are relative to `backend/apps/` unless prefixed otherwise. Presence means
authored code, not integration acceptance; [remaining work](events/integration-status.md)
must close before enabling the off-default programme features.

| Responsibility | Sole writer / adapter source |
| --- | --- |
| Feature declarations | `makerspaces/capability_definitions_events_programme.py`; five children of Events, no new module |
| Model discovery | `events/models_programme.py` explicit barrel; `accounts/models.py`, `encryption/models.py`, `organizations/models.py` discover independent models |
| Application lifecycle / prepared form ports | `events/hackathons/admission_workflow.py`, `admission_ports.py`, `admission_inputs.py`, `admission_projection.py` |
| Release/RSVP/expiry/capacity | `admission_decisions.py`, `admission_rsvp.py`, `admission_maintenance.py`, `capacity_admission.py`; existing `events/capacity.py` remains hard event/ticket math |
| Canonical ordinary-registration bridge | `events/hackathons/admission_bridge.py`, `admission_ports.py`; existing `services_registration.py`, `services_registration_state.py` own registration transitions; installed by `events/contracts/admission_registration.py` |
| Application review | `events/hackathons/review_workflow.py`, `review_projection.py`, `review_models.py` |
| Applications for any event (L21a) | `events/hackathons/admission_feature.py` (which switch opens the engine), `admission_transactions.admission_enabled` |
| Review stages (L21a) | `events/hackathons/admission_stage_models.py`, `admission_stages.py` (settings, panels), `admission_stage_assign.py` (seeded preview/apply), `admission_stage_review.py` (panel workspace), `admission_stage_flow.py` (advance, coverage, stale skips), `admission_webhooks.py`; routes in `events/urls_l21a.py` |
| Attendance, re-accept, crew, check-in lists (L21a) | `events/attendance_confirmation.py` + `tasks_attendance.py`, `services_registration_state.reaccept_registration`, `events/contributions/crew_workflow.py` + `crew_reads.py`, `events/checkin_lists.py`; per-event switches in `models_participation.py`; notices in `notices_r2_l21a.py`; route catalogue and native decisions in `accounts/programme_route_catalog_l21a.py` |
| Teams/invitations/finder/moderation | `events/hackathons/team_workflow.py`, `team_invitations.py`, `team_lifecycle.py`, `team_moderation.py`; never a second registration/quantity writer |
| Project draft, immutable submission | `events/submissions/workflow.py`, `snapshot_assets.py`, `models_projects.py`; moderation/triage via domain services |
| Upload and accepted bytes | `events/submissions/asset_workflow.py`, `asset_jobs.py`, `storage.py`, `storage_promotion.py`; immutable verified copy/hash before final promotion |
| File registry/validation | `maker_formats/registry.py`, `upload_policy.py`, bounded signature/XML/text/ZIP/image readers; `maker_file_formats.py` compatibility barrel keeps `legacy.py` policy |
| File quota | `events/submissions/quota.py`; `submissions/boundary_runtime.py` and `makerspaces/storage_events_programme.py` own dedicated receipt-backed accounting |
| Live private bytes | `makerspaces/private_upload_transport.py` model-free transport; B `read_policy.py` + D predicates choose server-owned purpose; no download presign shortcut |
| Scanner and video | `events/submissions/scanning.py`, `probing.py`, `probe_sandbox.py`; `contracts/asset_registration.py` installs scanner options and the non-root ffprobe launcher |
| Byte expiry / abandoned work | `events/submissions/retention.py`, `cleanup_schedule.py`, `upload_deadlines.py`, `storage_cleanup.py`; `models_assets.EventAssetObligation` retains exact cleanup custody after graph purge |
| Contributor authority and work | `events/contributions/role_workflow.py`, `role_policy.py`, `authority.py`, `ports.py`, `requirements_workflow.py`; entitlement sources separate from display role |
| Shifts/hours/contributor ticket/certificate eligibility | `events/contributions/shift_workflow.py`, `attendance_workflow.py`, `admission_adapter.py`, `certificate_subjects.py` |
| Mentor assignment/help/office hours | `events/mentoring/assignment_workflow.py`, `help_workflow.py`, `help_expiry.py`, `office_hours_workflow.py`, `configuration_workflow.py` |
| Mentor rounds / practice / analytics | `events/mentoring/round_workflow.py`, `analytics.py`, `import_export.py`; practice isolated from production side effects |
| Tracks, prizes, judging | `events/judging/definitions_workflow.py`, `round_workflow.py`, `assignment_planner.py`, `scoring_workflow.py`, `calculations.py`, `conflicts.py` |
| Pairwise judging (`events.pairwise_judging`) | `events/judging/models_pairwise.py` (comparison, invalidation, cursor), `pairwise_ranking.py` (**only** CrowdBT math, pure), `pairwise_assignment.py` (next-project choice, pure), `pairwise_projection.py` (replay, standings, the capability gate), `pairwise_workflow.py` (**only** pairwise writer), `views_pairwise.py`, `serializers_pairwise.py`; invalidation reuses `ballot_invalidation.py`; frontend `features/staff/hackathonJudging/{PairwiseJudge,PairwiseDesk,pairwiseApi}` |
| Result revision / announcement | `events/judging/results_workflow.py`; B retention anchor called on first announcement only |
| Sponsor résumé consent | **Only** `events/judging/sponsor_consent_workflow.py` and `ParticipantSponsorResumeConsent`; C/B consume it, never duplicate it |
| Gallery consent/publication/reads | `events/submissions/gallery_consent_workflow.py`, `gallery_workflow.py`, `gallery_projection.py`; D-owned frozen item selection and live consent |
| Pages programme projection | `events/programme_sections/providers.py`; requires actual pages registry and release/section gate, not a new website system |
| Opaque registration credentials | `events/credentials/crypto.py`, `workflow.py`, `resolution.py`; existing `services_checkin.py` remains attendance writer |
| Certificate issuance, revoke/reissue | `events/services_certificates.py` thin facade; `certificates/issuance.py`, `subjects.py`, `lifecycle.py`, `tasks.py` |
| Public certificate verification | `events/certificates/verification.py`, `publication.py`; public event/date/status independent of private PDF authority |
| Layered templates, library and print | `events/certificates/layout.py`, `rendering.py`, `library_capture.py`, `badge_designs.py`, `print_workflow.py`, `print_cleanup.py`; common `operations/printable_*` remains model-free |
| Selected profile/photo | `events/profile_photos/selection_workflow.py`, `policy.py`, `snapshot.py`; source remains `makerspaces/models_profiles.py` + `profile_images.py` |
| Default templates/artwork | `events/default_templates/` versioned catalogue; `certificates/seeds.py` validates catalogue, `programme_runtime.py` installs read provider; `seed_installation.py` owns immutable copies, `seed_views.py` previews/installs |
| Shared forms and profile keys | `forms_schema/` is the single v1/v2 validator and `profile_fields.py` registry; `events/programme/forms.py` manages immutable form definitions; `registration_form_adapter.py` normalizes ordinary admission |
| Saved details and account assets/export | `accounts/saved_details/` owner-only workflows, prefill, intents, résumé copy, cleanup; no Events import in the independent vault |
| Always-encrypted account keys/fences | `encryption/account_services.py`, `account_readiness.py`, `account_write_fence.py`, `account_mappers.py`, `account_models.py` |
| DOB and date review | `events/answer_derivations/` encrypted sources/history for registration, application and role assignment; account DOB copied into independent tenant-owned evidence |
| Programme commands/live/readiness/publishing | `events/programme/commands.py`, `aggregate.py`, `readiness.py`, `live.py`, `publishing.py`, `providers.py` |
| Broadcast composer/recovery | `events/programme/broadcast_*`, `events/broadcast_channels.py`; `integrations/broadcasts_worker.py` owns shared batch mechanics |
| Extra account/platform surfaces | `accounts/security_activity.py`, `organizations/member_leave.py`, `operations/platform_insights.py`; mounted independently of Events |

## Staged forms, travel support and core payouts

| Responsibility | Sole writer / adapter source |
| --- | --- |
| Stage definitions, assignments, responses | `events/staged_forms/stage_workflow.py`, `response_workflow.py`, `lifecycle.py`, `trigger_service.py`; mounted by `events/urls_member.py`/`urls_admin.py` |
| Inline signup blocks (stage forms + request) | `events/inline_forms.py` prepares outside and binds inside the outer registration (`services_registration.py`) or application (`hackathons/admission_workflow.py`) transaction; R halves are `staged_forms/inline_submission.py` and `event_reimbursements/request_form_adapter.py` + `request_workflow.submit_application_locked` |
| Stage readiness guard | `events/staged_forms/guards.py` via `admission_hooks.require_action_locked`; called by `services_checkin.mark_attended_locked` (every source, offline sync reports `stage_incomplete`) and `hackathons/admission_rsvp.rsvp` |
| Saved-details binding/prefill for stage responses | `events/contracts/admission_registration.py` (one installed binding dispatching `stage_response` to `staged_forms/prefill_provider.py`) and `contracts/prefill_registration.py` |
| Attendance → payout eligibility | `events/attendance_payout_bridge.py` (attendance revision, `EventAttendanceCorrection` marker, claim republish) |
| Travel support domain | `event_reimbursements/` (programme, pools, requests, awards, claims, decisions); mounted separably in `config/urls.py` |
| Core payout ledger | `payments/event_payouts/` (obligations, encrypted payee revisions, payouts, attachments, retention); ports installed by `payments/event_payout_bridge.py` |
| Notices and reminders | stage/payout notification sources in `events/notification_sources.py` and `payments/event_payout_bridge.py`; reminder sources in `operations/reminder_registry.py` |
| Tenant migration of these rows | `tenant_migration/catalog_reimbursements.py` (dispositions), `semantic_reimbursements.py`, `pii_reimbursements.py`, `import_pointers.py`, `reimbursement_assets_import.py`, `target_projection_reimbursements.py`, `unique_values_reimbursements.py`; byte closure in `makerspaces/storage_keys_reimbursements.py` |
| Archive impact and purge preflight | `makerspaces/lifecycle_archive.archive_impact` (unpaid event payouts); `makerspaces/module_purge_collectors_reimbursements.preflight_report` behind `purge_module_data --preflight` |

## Retention and runtime have different lifetimes

Retention declarations survive Events tombstoning: `encryption/registry_events_programme.py`,
`data_export/fields_events_programme.py`, `credentials_events_programme.py`,
`tenant_migration/catalog_events_programme*.py`, `unique_values_events_programme.py`,
`target_projection_events_programme.py`, `semantic_events_programme.py`, `pii_events_programme.py`,
`authority_events_programme*.py`, `audit_references_events_programme.py`,
`backup/main_projection_events_programme.py`, `makerspaces/purge_events_programme*.py`
and `storage_keys_events_programme.py`. They name retained rows, ownership and cleanup;
they do not authorize live workflows. `tenant_migration/event_asset_import.py` publishes verified target accounting; typed encrypted answers rebind target AAD.

`backup/object_reference_retention.py` owns typed object-capture projections for Evidence,
SubmissionAsset, HackathonParticipantAsset and MemberSavedAsset. Event assets use direct
state/expiry/canonical byte/hash fields, not Evidence's retention relation. Missing ready
bytes fail capture; terminal expiry permits expected absence. `object_reference_certificates.py`
tracks embedded artwork. Existing backups have their own retention/custody policy.

Runtime mounts: `events/urls_programme.py` via `config/urls.py`'s separable Events mount;
`accounts/urls_programme.py` independently mounts Saved details, own activity/organization
leave and platform insights. Exact-origin/claim/session/delegation/API-client declarations
remain mandatory for every named method. `events/apps.py` invokes `programme_runtime.py`
only while Events is active. `contracts/registration.py` composes A/B/C/D/E/F/P providers and source-backed notices; Accounts independently installs the core F profile-key provider.

`events/programme_locks.py` supplies declared combined fences and live authority locks
without locking User/key rows after Event. It does not prove legacy callers migrated.
`tasks_programme.py`, `tasks_contributions.py`, `reminders_programme.py`,
`programme/broadcast_schedule.py`, `accounts/saved_details/tasks.py` participate in
`backend/config/settings.py` beat schedule and
`operations/management/commands/run_scheduled_tasks.py`. Asset/certificate/print/judging recovery is scheduled; `tasks_retention.py` grants only retained byte cleanup, never workflow authority.

## Frontend and verification

Exports live under `frontend/src/features/events/{hackathonAdmission,hackathonSubmissions,
contributions,hackathonGallery,eventPresentation}/`, `features/staff/{hackathonAdmission,
mentorDesk,hackathonJudging,eventCredentials,eventProgramme}/`, `features/forms/`,
`features/accountSavedDetails/` and `components/delight/`. Original themed SVGs live in
`src/assets/illustrations/`; generic print controls in `components/print-layout/`.
The programme router, AppShell/drawer and real read contracts are mounted. Type/jsdom checks still require actual browser/privacy/provider verification. The [artwork inventory](events-programme-artwork-inventory.md)
records local proofs separately from E's authoritative rendering.

Tests live in `backend/tests/events/programme/`, `tests/maker_formats/`,
`tests/accounts/saved_details/`, `tests/encryption/account_scope/`, affected backup/tenant
migration/tombstone suites, and frontend beside-code files. These local tests can be ignored
by git; preserve them explicitly at owner handoff. The [acceptance table](events/acceptance.md)
links concrete files/routes and marks unexecuted evidence. No runtime test pass is claimed here.
