# SpaceWorks domain and frontend source map

Continued from [SOURCE-MAP.md](SOURCE-MAP.md); paths are relative to the repository root.

`makerspaces/capability_eligibility.py` shares configuration prerequisite checks between
`platform.feature_enabled` and batched live tenant discovery, with recovery
exclusions applied in SQL rather than queried per tenant.

- `backend/apps/hardware_requests/` — Hardware Request Workflow: `HardwareRequest`/`HardwareRequestItem`,
  `HardwareRequestItemAsset` through-model, immutable `ReturnEvent`/`RequesterAccountability`,
  `PublicToolLoan`, `PublicProblemReport`. `workflow.py` is the **single source of truth** for state
  transitions (atomic + row-locked + audited; also `assign_box`/`issue_request`/`return_items`);
  `permissions.py`, `exceptions.py` (workflow→HTTP map + `ErrorSerializer._EXCEPTION_MAP`),
  `notifications.py` (equipment envelope adapter barrel), public submit/verify/status views,
  `send_return_reminders` command. Equipment source/room/contact helpers are indexed in
  [SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md).
  `self_checkout_workflow.py` re-exports the issue and return services from `self_checkout_issue.py`
  and `self_checkout_returns.py`, with shared evidence checks in `self_checkout_evidence.py`.
  All return paths use `return_helpers.finalize_return_status`, which schedules the post-commit
  loan charge seam in `loan_payments.py` only when the request closes.
  Phase 9c replay: `models_replay.py` owns omitted command coordination; `replay_authorization.py`
  reloads the human lease and live policy; `replay_serializers.py`/`replay_payload_serializers.py` and
  `replay_fingerprint.py` normalize the protocol; `replay_prepare.py` establishes evidence/ownership;
  `replay_claims.py` fences claims; `replay_execute.py`/`replay_dispatch.py` wrap the shared online
  dispatcher and workflow transaction. `replay_views.py` is mounted by makerspaces/station_urls.py;
  `replay_cleanup.py`/`tasks_replay.py` implement bounded daily cleanup, with settings checks in checks.py.
  `evidence/finalization_completed.py` supplies database-only finalized reuse under domain locks.
  `frontend/src/features/kiosk/kioskReplayApi.ts` hand-writes typed prepare/execute calls using only
  Station cookie + human lease; `kioskReplayClient.ts` now owns encrypted foreground/SW replay.
  The staff recovery screen remains phase 9e.
- `backend/apps/payments/` — permanently core Payment/ManualSettlement ledger, reconciliation,
  member history and receipts. `availability.py` separates `charges.*` recording from online checkout.
  `backend/apps/payments_rail/` owns removable provider-facing routes (checkout, native intents,
  Connect, refunds and webhooks); shared provider services retain their established payments paths.
  These include per-space credentials, managed Stripe Connect resolution and provider settlement.
  `services_checkout.py` is the explicit compatibility barrel over `checkout_coordination.py`
  (credential/payment locks) and `checkout_provider.py` (provider requests and currency helpers).
  `services_webhooks.py` re-exports Connect handling from `services_connect_webhooks.py`;
  `notifications.py` supplies bounded payment snapshots to the feature/channel matrix.
- `backend/apps/bookings/service_payments.py` — required local debt creation/cancellation
  inside the existing atomic booking workflows; optional checkout is scheduled after
  commit and provider failures remain best-effort through payment reconciliation.
  BK-0 regression coverage lives in `tests/bookings/test_payment_ledger_rollback.py`
  and `test_payment_provider_boundary.py`, sharing `payment_ledger_helpers.py`;
  `tests/payments/test_track3_booking_event_charging.py` separates required debt failure
  from optional checkout failure.
- `backend/apps/printing/` — **TOMBSTONED** (Project B): only an `AppConfig` and an empty `models.py`, kept
  in `INSTALLED_APPS` so its historical migrations remain installed. 3D printing is now a `MachineType`
  inside `apps/machines/` — look there, not here.
- `backend/apps/roadmap/` — **TOMBSTONED**: `RoadmapItem` retained for migration history only. No URLs,
  serializers, admin surface or frontend; `tests/roadmap/test_removed_surfaces.py` asserts they stay removed.
- `backend/apps/machines/` — machine registry and service workflows. Machine-role authorization keeps a
  thin `role_scope.py` import surface over `role_scope_resolution.py` (including the identity-sensitive
  `EXEMPT`/`NOTHING` sentinels), `role_scope_grants.py`, and `role_scope_queries.py`.
  `models_membership_scope.py` stores per-person machine-type links; `member_scope_services.py`
  writes them. The removed `role_scope_services.py` no longer owns role-level scope.
- `backend/apps/events/` — the separable events module. `models.py` is the stable explicit re-export barrel.

  The programme's additional model barrel, workflow writers, retained registries and
  pending runtime adapters are indexed in [SOURCE-MAP-EVENTS-PROGRAMME.md](SOURCE-MAP-EVENTS-PROGRAMME.md).
  The ordinary-event files below remain the compatibility surface; new domain code does
  not replace canonical registration, capacity or attendance with independent writers.

  Its ordinary-event imports cover `models_event.py`, `models_registration.py`, `models_attendance.py`, `models_feedback.py`,
  `models_station.py`, `models_certificates.py`, `models_series.py`, `models_calendar.py`, `models_collaborators.py` and
  `organizer_models.py`; those focused files are the schema sources for events/occurrences, approval and
  waitlist registrations, immutable check-in history and the event-owned `EventStationBinding`, feedback,
  certificate artifacts,
  recurring series, member feed credentials, makerspace collaboration and organization attribution.
  `organization_audience.py` adapts the core organization membership predicate and locks its
  live proof (its candidates read `audience_models.py`'s `EventAudienceOrganization`, written only by
  `services_audience_organizations.py` via `views_audience_organizations.py`); `directories.py` /
  `views_directories.py` serve the staff organization and partner-makerspace directories, and
  `views_checkin_history.py` the check-in-only "who has checked in" list, all routed by `urls_partners.py`; `host_waivers.py` owns transactional current consent and audited stamping.
  `serializers_organization_audience.py` / `views_organization_audience.py` separate public
  attribution from private eligibility; `views_registration_calendar.py` serves exact-owner ICS.
  `registration_locks.py` shares the event/source fence and registration locks.
  `services_core.py` / `services_event_details.py`, `services_series_templates.py` /
  `services_series_update.py` and `services_attendance_correction.py` keep mutations below
  the ceiling behind explicit service barrels. `serializers_event_details.py` and
  `serializers_admin_responses.py` split read/envelope contracts behind the existing barrel.
  `services.py` remains the audited transactional boundary for one-off event and registration mutations,
  delegating lifecycle and registration-state transitions to `services_lifecycle.py`,
  `services_registration.py` and `services_registration_state.py`. The other `services_*` modules own the
  corresponding series/recurrence/collaboration, calendar/feed, badge, check-in/offline-sync and the event
  policy adapter over the makerspaces Station core,
  feedback/certificate, image and organizer workflows; `urls_admin.py`, `urls_member.py`, `urls_public.py`
  and `urls_station.py` divide the staff, authenticated-member, public and anonymous-station surfaces.
  `registration_access.py` owns audiences; `invites.py`, `ticketing.py` and `promos.py` own
  hashed credentials, ticket eligibility and copied series templates. `serializers_registration_admin.py`
  contains the registration contracts re-exported by `serializers_admin.py`;
  `serializers_ticketing_public.py` shares discovery fields between public and partner events.
  `views_public_detail.py` reuses the public contract; `urls_ticketing.py` owns staff ticketing routes.
  `services_registration_tools.py` owns validated answer edits and exact cancellation undo;
  `services_clone.py` copies draft configuration and independently owned covers without grants
  or participation. `feedback_templates.py` supplies starter surveys and refuses replacement
  after responses. `services_series_admission.py` locks the complete organization-audience
  source set before a series update or waiter promotion. `views_ticket.py` serves exact-owner
  ticket details/PNG downloads; `views_registration_calendar.py` serves the owned ICS file.
- `backend/apps/warranty/`, `apps/maintenance/`, `apps/events/`, `apps/bookings/`, `apps/forms_schema/`,
  `apps/encryption/`, `apps/procurement/`, `apps/notifications/`, `apps/operations/report_registry.py` — the
  remaining FabLab + governance modules.
- `backend/tests/` — pytest behavior tests (external behavior, not implementation).
- `frontend/src/features/inventory/` — public catalog/detail/self-checkout + `ProductCard`/
  `AvailabilityBadge`. `frontend/src/features/staff/` — staff console panels; grouped nav via
  `staffAccess.ts` `TAB_GROUPS`, which does sidebar grouping AND permission derivation (**not**
  `StaffApp.tsx`; module gating and routing are the separate `staffTabs.ts`); capabilities from
  action-based `staffAccess.ts`; payment reconciliation and platform credential panels.
  `MakerspaceProfileSettings.tsx` loads/saves the location and hours profile;
  `MakerspaceHoursEditor.tsx` and `makerspaceProfileForm.ts` own the weekly/exception
  draft. Profile and payment editors refresh each other's shared currency query.
  `frontend/src/features/auth/` + `members/MemberAuthPanel.tsx` — provider-config-driven social/member auth.
  `frontend/src/features/printing|bookings|forms|...` — feature slices. `frontend/src/lib/`,
  `components/ui/`, `types/`, `generated/api.ts`.
- `frontend/src/features/events/` — the standalone anonymous PIN-station route. Its
  `EventCheckInStationPage.tsx` exchanges the event-scoped PIN, then reuses the offline roster/sync API,
  IndexedDB state and operator UI owned by `features/staff/eventCheckInOfflineApi.ts`,
  `eventCheckInOfflineStore.ts` and `OfflineCheckInOperator.tsx`.
- `frontend/src/features/kiosk/` — Station shell, selected offline handover and queue status.
  `offlineQueueStore.ts`/`offlineQueueDb.ts` own atomic encrypted work/commands/evidence,
  cross-context locks, caps and expiry; `offlineEvidence.ts` owns pixel normalization.
  `replayPolicy.ts` owns scheduling/backoff and typed authority/domain distinctions.
  `frontend/src/lib/encryptedIndexedDb.ts` supplies storage/crypto mechanics shared
  with the legacy event adapter, whose database/wire format remains unchanged.
  `frontend/src/sw.ts` owns kiosk app-shell fetch policy and opportunistic encrypted
  Background Sync. `frontend/scripts/kiosk-pwa.ts` bundles it through Vite and injects
  final asset revisions; `verify-pwa-build.mjs` checks emitted artifacts. Static
  `public/sw.js` is removed. The offline rules live in `docs/KIOSK-OFFLINE.md`.
  Failed handover recovery lives in `hardware_requests/replay_recovery_*` and
  `features/kiosk/KioskReplay*`; its review, correction and retention contract is
  documented in `docs/KIOSK-RECOVERY.md`. `operations/e2e_kiosk_seed.py` supplies
  isolated real-workflow fixtures; `dev.sh e2e` runs Playwright against a production preview.
- `frontend/src/features/organizations/` — public organization presentation and invitation redemption:
  `PublicOrganizationPage.tsx` renders the public profile and paginated cross-makerspace event catalogue,
  `OrganizationInvitationRedeemPage.tsx` binds a single-use invitation after member sign-in, and
  `publicOrganizationsApi.ts` owns their TanStack Query keys and public API calls. Staff profile,
  membership, invitation and event-organizer controls remain under `frontend/src/features/staff/`.

Tenant branding lives in `frontend/src/lib/brandColours.ts` (WCAG checks and
light/dark palette derivation) and `useTenantBranding.ts` (page-scoped variables).
See [SOURCE-MAP-CLIENT.md](SOURCE-MAP-CLIENT.md) for the theme settings preview,
shared component styles, browser theme preference and tenant support links.

## Connected device monitoring (phase 7d lane)

`apps/devices/services_offline.py` owns the per-tenant offline/retention scan and the locked
activity/recovery hook. `tasks.py` exposes its one-minute scheduled entry; `notifications.py`
builds immutable edge-time snapshots for the existing staff notification fan-out.
`integrations/email_templates_registry_devices*.py` owns the staff-only devices stream.
`tenant_migration/gate_policy.py` re-exports HTTP, task and object catalogs from the corresponding
`gate_policy_http.py`, `gate_policy_tasks.py` and `gate_policy_objects.py` siblings.

Frontend `StaffTabLoaders.tsx` holds lazy imports; `StaffPlatformTabContent.tsx` composes platform/admin
panels. `panels/DevicesPanel.tsx`, `DeviceIdentitySection.tsx` and `DeviceEnrollmentModal.tsx` render
7a identity/status/enrollment controls through `devicesApi.ts` and `deviceQueryKeys.ts`.
Printer adapter and label-command controls require the sibling 7b/7c lanes and are not present here.

Booking resource authority (BK-A): `bookings/booking_authority.py` and
`booking_permissions.py` centralize live tenant/resource policy and permission vocabulary;
`booking_authority_page.py` batches list-response authority to avoid per-row grant queries;
`models_staff_grants.py`, migration `0012_booking_staff_grants.py`,
`services_staff_grants.py`, `serializers_staff_grants.py`, `views_staff_grants.py`,
`views_grant_pagination.py` and `urls_staff_grants.py` adapt the shared invitation lifecycle.
`staff_payload.py` registers booking-only workspace discovery; `views_accessible_spaces.py`
serves a paginated live resource list. Existing space/booking/recurrence services enforce
policy under their resource locks. `makerspaces/resource_grant_locks.py` supplies shared
local-role/account/organization delegation locks, used by the event adapter too.

Frontend: `bookingStaffGrantsApi.ts`, `BookingStaffAccess.tsx`, `BookingPermissionFields.tsx`
and `BookingStaffInvitePage.tsx` own grant server state, management and acceptance;
`GrantedBookingSpacesPanel.tsx` joins event assignments in the narrow workspace.
`bookingStaffPermissions.ts` gates `BookingDrawer.tsx` actions; `BookingDetailsEditor.tsx`
submits descriptive fields only. Query keys include resource IDs and page/filter state;
grant mutations invalidate access lists and resource detail, booking mutations retain the
existing reservation/availability/report invalidation. Backend tests for this lane live
under `backend/tests/bookings/test_resource_*` (gitignored per repository convention).

Booking staff tools (BK-B): `bookings/admission.py` shares ordinary current admission
between creation, exact undo and validated moves; approval keeps its existing policy.
`services_staff_edit.py` owns note/answer edits and the locked movement boundary used
by staff and member rescheduling; `services_restore.py` adapts the always-present
`operations/cancellation_restore.py` contract. Cancellation provenance lives on
`models_booking.py` (migration `0013_booking_cancellation_provenance`).
`services_clone.py` declares copyable configuration and owned cover copying through
`makerspaces/resource_clone.py`; `resource_clone_extensions.py` registers child-copy
adapters without importing separable apps. `serializers_staff_tools.py`,
`serializers_reservation.py` and `views_staff_tools.py` supply strict inputs and scoped
staff routes, re-exported by the existing barrels where appropriate.
`BookingReservationEditor.tsx`, `BookingCloneControl.tsx` and `bookingToolsApi.ts`
provide staff controls/cache invalidation. `BookingDrawerTabs.tsx` supplies the drawer
extension slots for later lanes. Restored lifecycle catalog/defaults remain in the
normal integrations template registry; no second notification dispatcher is created.

## Booking communications (BK-D)

- `bookings/models_broadcasts.py`: concrete resource campaigns and unique account deliveries.
- `broadcasts.py`, `services_broadcasts.py`: typed shared-engine adapter and audited draft/queue/cancel policy.
- `communication_recipients.py`: current verified account email, optional membership consent and notification policy.
- `reminders.py`, `reminder_delivery.py`: account-only discovery, occurrence claims and live pre-send adapter.
- `serializers_broadcasts.py`, `views_broadcasts.py`, `urls_broadcasts.py`: resource-authorized staff compose/history/actions.
- `migrations/0016_booking_broadcasts.py`: history schema and persistent PII write-fence trigger, after the merged pass-template leaf 0015.
- `integrations/delivery_sources.py` retains source requirements across tombstones; `broadcasts_delivery.py` skips render-time eligibility loss. Shared digest/worker implementations remain in Integrations; Bookings never imports Events.

## Event website and reusable public serving (Lane C)

- `events/models_website.py` owns `EventPage`, private assets, typed sections, sessions and
  session-speaker links. `services_website.py` owns locked editor/release/delay writes;
  `services_website_assets.py` owns asset row mutations. `website_copy.py` extends Lane B's
  clone adapter and provides occurrence copy-on-write. `website_validation.py` protects
  owner-window changes; migrations 0032/0033 enforce cross-row ownership and windows.
- `events/website_visibility.py` owns the core and enhanced event gates;
  `website_projection.py` owns the allow-list schedule/section projection and delays.
  `website_adapter.py` registers the concrete event adapter. `serializers_website*.py`,
  `views_website_admin.py`, `views_website_public.py` and `urls_website.py` own its REST surface.
- Shared always-present `makerspaces/website_assets.py` owns bounded private WebP staging,
  quota and cleanup; `website_uploads.py` bounds multipart ingress before spooling.
  `website_visibility.py` is the adapter registry;
  `website_directory.py` owns directory/origin/canonical URL policy;
  `website_origins.py` validates framing trust. `website_serving.py`, `website_views.py`,
  `website_settings_views.py` and `website_urls.py` own embed/share/discover/sitemap/robots
  serving and tenant framing settings. These modules never import either separable domain.
- `tenant_migration/catalog_website.py` and `unique_values_website.py` declare website
  retention and uniqueness; existing export, projection, backup, storage and purge registries
  bind the concrete models. Portable import clears release/framing authority, retaining
  object-journal ownership proof for imported bytes.
- `features/staff/EventWebsiteEditor.tsx`, `EventWebsiteSections.tsx`,
  `EventWebsiteSchedule.tsx`, `EventWebsitePublication.tsx` and `eventWebsiteApi.ts` own
  the event/series drawer controls, component drafts and TanStack Query invalidation.
  `WebsiteEmbedOrigins.tsx` sits in public-site settings. `features/events/PublicEventWebsite.tsx`
  and `EventDiscoverPage.tsx` render released content and deployment discovery.
  `components/RestrictedMarkdown.tsx` is the safe text vocabulary;
  `PublicWebsiteImage.tsx` and `staff/PrivateWebsiteImage.tsx` own the authorized blob transports.

Lane C content completion: `events/website_content.py` owns the canonical group/tier vocabulary;
`serializers_website_content.py` owns typed venue, URL, coordinate and layout validation.
The existing `services_website.py`, `website_projection.py` and `website_copy.py` persist,
filter and copy that content through the same authority and private asset pipeline.
