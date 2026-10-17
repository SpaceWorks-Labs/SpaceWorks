# SpaceWorks source map

> **This is the file-layout half of `CLAUDE.md` / `AGENTS.md`.** It was split out when that file crossed
> the harness's memory-file size limit; nothing was dropped in the move. It has no `AGENTS.md`-style twin —
> both names of that document point at this one path, so edit it in place.
>
> Paths drift. If this disagrees with the tree, the tree wins — fix this file in the same commit.

## Current source map (real paths)

Public-image POST/PUT presigns live in `inventory/public_image_storage.py` and
`bookings/storage.py`; both delegate bounded validation and conditional, write-once promotion
to `inventory/public_image_promotion.py`. Membership owner mail is classified as staff/account
or community in `makerspaces/notifications_p2_members.py`; `operations/notifications_p2.py`
keeps the owner route separate from the existing staff-summary category.

The design revamp shell lives in `frontend/src/components/shell/` (barrel `index.ts`):
`AppShell` composes the desktop `Sidebar`, `SidebarSection`/`SidebarItem`,
`WorkspaceSwitcher`, `UserMenu`, `MobileTopBar`, `SidebarDrawer`, `BottomTabs` and
`JobTrayPill`. The logo/switcher/search and user chip frame one scrolling navigation
region, including Settings and Platform. The shell uses the wave-1 brand tokens and
`SpaceWorksLogo`; reusable UI primitives remain in `components/ui/` (`index.ts`).
Every routed screen renders exactly one page layout from `components/layouts/` (barrel
`index.ts`): `DashboardLayout`, `ListLayout`, `DetailLayout` (page or drawer), `SettingsLayout`,
`FormPageLayout`, `FlowLayout` (page, dialog or kiosk), `AuthLayout`, `CenteredCardLayout`,
`PublicLayout`, `PublicDetailLayout` and `KioskLayout`; layouts own geometry, landmarks, the
single `h1` and loading/error/empty switching, and contain no gating. Shared primitives
(`PageHeader`, `Tabs`, `StatCard`, `ListRow`, `DateChip`/`IdentityChip`, `StatusPill`, `Callout`,
`SettingsRow`, `DangerZone`, `ActivityRail`, `TicketCard`, `ScanWorkbench`, …) are documented in
`docs/design-revamp/DR-PRIMITIVES.md`. Design source of truth: `docs/brand/` (brand guidelines v1 +
logo masters) and `docs/design-revamp/` (plan, UI/UX specs); the same assets ship in the
`SpaceWorks-HQ/SpaceWorks-Design` repository for use as a submodule.

`features/staff/sidebarSections.ts` owns the 42-key sidebar presentation map;
`StaffShell.tsx` adapts the existing permission/module-filtered tabs, shared Inbox unread
query, cached dashboard counts and machine-type cache. `StaffWorkspace.tsx` retains
canonicalisation and `StaffListContext`; `StaffApp.tsx` retains its pre-shell gates.
The picker stays outside the shell (S10); global routes use its no-workspace mode.
`StaffHeader.tsx`, `StaffDock.tsx`, `StaffDockPopover.tsx`, `useDockAnchor.ts` and
`staffNavIcons.tsx` were removed. `CommandPalette` stays mounted across drawer closure;
`JobTray` keeps job polling alive behind its compact pill and unmounts closed dialog controls.
`features/members/MemberPortalTabs.tsx` composes the member `AppShell` from the unchanged
`memberTabs(modules)` selector, using URL navigation links and the shared `#main-content`
skip target. `MemberArea.tsx` supplies workspace/account data and unchanged tab bodies.
BK-H signed booking reads are mapped in
[SOURCE-MAP-BOOKING-READS.md](SOURCE-MAP-BOOKING-READS.md). They use the existing core
HMAC, typed-target, cursor and re-auth contracts; Events is never imported.

BK-F resource websites are mapped in [SOURCE-MAP-BOOKING-WEBSITES.md](SOURCE-MAP-BOOKING-WEBSITES.md).
Bookings supplies typed adapters to the always-present website/asset/clone infrastructure.

BK-G printable passes are mapped in [SOURCE-MAP-BOOKING-PASSES.md](SOURCE-MAP-BOOKING-PASSES.md).
They consume the existing core positioned-layout/PDF primitives without importing Events.

BK-C booking arrival is isolated in `bookings/models_arrival.py` (abstract credential /
projection fields and append-only history), `services_arrival.py` (resolve/confirm/reverse),
`services_arrival_policy.py` (locked lifecycle/time-edit matrix) and `arrival_projection.py`
(minimal scanner DTO and BK-E aggregate query). The existing Booking save boundary invokes
the guard so BK-B's ordinary service saves consume it without duplicating BK-B tools.
`confirmation_access.py`, `confirmation_render.py`, `serializers_arrival.py`,
`views_confirmation.py`/`urls_confirmation.py` and `views_arrival.py`/`urls_arrival.py`
own private confirmations and scanner endpoints. `calendar_render.py` is the shared booking
feed/single-ICS serializer; PNG/calendar formatting reuses always-present
`makerspaces/confirmation_render.py`. `makerspaces/confirmation_secrets.py` supplies neutral
QR log redaction; `confirmation_privacy.py` applies private headers through the existing
request-ID middleware and handlers, including errors before view dispatch. `tenant_migration/catalog_booking_arrival.py` declares portable arrival
facts; credential omission/fresh reconstruction, User closure, datasets and purge are wired
in their existing registries. No stored asset is introduced.
Frontend `bookings/BookingConfirmation.tsx` + `bookingConfirmationApi.ts` provide private
QR/download/rotation controls; `staff/BookingArrivalScanner.tsx` uses the shared camera
scanner plus manual entry and explicit resolve/confirm/reverse controls. The drawer combines the BK-B tab shell and staff tools with the BK-C scanner.
Roster `arrived_at` hides unavailable edits/cancellation/no-show actions; completion remains
independent of arrival. MyBookings, public submission and the
public bookings page link to owned confirmations without carrying a QR in navigation URLs.

Lane D shared communications live in `integrations/broadcasts_models.py` (abstract schema),
`broadcasts_registry.py` (typed adapters), `broadcasts_worker.py` (200-account batches and
recovery), `broadcasts_delivery.py` (execution checks/status reconciliation) and
`broadcasts_preferences.py` (shared saved-category routing for event and booking campaigns).
Phase-1a personal notification contracts live in `integrations/models_contract.py`,
`models_endpoints.py`, `notification_outbox.py`, `notification_resolution.py`,
`notification_delivery.py`, `notification_proofs.py` and their `notification_*` siblings.
`notifications/models_preferences.py` owns personal multi-select policy; the existing
`integrations.NotificationPreference` still owns the tenant matrix. Domain lanes register
live validators/renderers with `notification_sources.py`; provider lanes register factories
through `notification_providers.py`. HTTP shapes and proof requirements are frozen in
`docs/notification-contract.md`, with the Phase-2 trigger target in `docs/notification-coverage.md`.
`delivery_sources.py` is the pre-send/digest eligibility registry; `delivery_digest.py`
rebuilds summaries from durable source outbox references. `EmailDelivery` and `EmailLog`
carry source kind/id/metadata through lifecycle dispatch, deferral and retry.
`operations/report_subjects.py` owns generic subject validation/authorization;
`report_download.py` dispatches registered CSV/XLSX/PDF renderers and download audits.
`report_pdf.py` renders paginated metric/value tables with provenance; new event report
definitions/builders/typed contracts are `report_definitions_events.py`,
`reports_event_exports.py`, `serializers_reports_events_detail.py`.

Booking resource reports (BK-E): `bookings/report_subject.py` registers the typed
`bookable_space` policy; `report_features.py` projects request-local UI capabilities.
`operations/report_definitions_bookings.py` registers four tenant-only reports;
`reports_booking_resources.py` reuses `reports_bookings.py` and wires
`extend_with_booking_arrival_counts` to BK-C `arrival_projection.arrival_metrics`,
using the same tenant/resource/overlap window. Resource rows and exports include separately
labelled current arrival counts; legacy tenant reservation utilisation is unchanged. `reports_booking_exports.py`
reads allow-listed reservation/contact and answer snapshots through model accessors;
`serializers_reports_bookings.py` defines the typed response contracts, including the
resource-only arrival-count row.
`reports_booking_pdf.py` supplies reservation semantics to the shared renderer;
`report_pdf_fonts.py` selects the embedded Unicode font (backend image: DejaVu Sans).
`BookingResourceAnalytics.tsx`, `BookingResourceTabs.tsx` and `bookingReportsApi.ts`
provide resource/date query keys, accessible drawer tabs and audited download actions;
`OperationsReportsBookings.tsx` exports the summary shared with the existing tenant report.
Regression tests live under `backend/tests/operations/test_booking_*reports.py`,
`test_booking_report_exports.py` and `test_booking_arrival_reports.py`; staff/arrival matrix regressions live in
`backend/tests/bookings/test_arrival_staff_tools_integration.py`. The resource analytics
Vitest file covers separately labelled arrival counts.

Event adapters live in `events/broadcasts.py`, `models_broadcasts.py`,
`services_broadcasts.py`, `views_broadcasts.py`, `serializers_broadcasts.py` and
`urls_communications.py`; `services_bulk_invites.py`/`views_bulk_invites.py` own the
bounded code-free email invitation flow, and `report_subject.py` owns event report policy.
`makerspaces/module_purge_collectors_events.py` is re-exported by the existing collector
barrel; `tenant_migration/catalog_broadcasts.py` declares inert portable history.
Staff drawer components are `EventBroadcastsPanel.tsx`, `EventBulkInvites.tsx` and
`EventAnalyticsPanel.tsx`, backed by `eventCommunicationsApi.ts` query keys/mutations.

Event staff authority lives in `events/event_authority.py`, with its permission vocabulary
in `event_permissions.py` and concrete typed event/series grants in `models_staff_grants.py`.
`services_staff_grants.py` adapts the always-present
`makerspaces/resource_grants_services.py` invite lifecycle; abstract fields and validation
are in `makerspaces/resource_grants_models.py`. `resource_grant_sources.py` is the query-free
runtime discovery registry consulted by account sign-in, auth payloads and MFA. Events
registers its `staff_payload.py` source only while active; retention and purge continue
to own concrete event rows after tombstoning. `views_staff_grants.py`,
`serializers_staff_grants.py` and `urls_staff_grants.py` own invite/grant management and
redemption; `views_accessible_events.py` lists only events the actor can access.
`registration_view_errors.py` holds registration error schemas shared by the registration
and eligible-member views, keeping their imports independent.
`staff_grant_locks.py` stabilizes creator authority under user, role, membership and organizer
locks; `serializers_event_authority.py` adds the shared permissions/manager projection to
event and series serializers. `event_authority_page.py` resolves list-page authority in
batches; list views pass its results through serializer context, while details keep
per-object checks. Discovery includes series entries with `event_id=null`,
so a granted series remains reachable before it has occurrences.
Fixed membership roles live in `makerspaces/role_catalog.py`. `accounts/rbac_roles.py`
shares the valid-role predicate between object resolution and SQL `Exists` filters;
`makerspaces/role_membership_writes.py` is the complete-set writer used by lifecycle
and staff assignment services. Machine authority links are per membership and type in
`machines/models_membership_scope.py`, resolved by `role_scope_resolution.py` and
written by `member_scope_services.py`. The console API lives in
`admin_api/views_member_scope.py` and `serializers_member_scope.py`.
Frontend `features/staff/panels/RoleSetPicker.tsx` owns exclusive/combinable checkbox selection;
`roleSets.ts` owns assignment ceilings, handwritten membership role-set types and cache invalidation.
`RolesReference.tsx` renders the read-only server role catalogue. `MemberRolesControl.tsx` saves
community-roster role sets; `MemberMachineTypes.tsx` edits per-person type scope using `rolesApi.ts`.
Users/AddStaffModal reuse the picker; UsersTable and MembersPanel display the whole role set.
Role CRUD and RoleManager/RoleEditor/RoleMachineScopeEditor are removed. Booking rules reuse
`MakerspaceBookingRulesSettings.tsx` in both Settings and Bookings.

WP1 event access and ticketing lives in `events/registration_access.py`, `invites.py`,
`ticketing.py` and `promos.py`; `participant_access.py` limits account ticket reads to
the owned registration. New model, serializer and route files are indexed in
[SOURCE-MAP-DOMAINS.md](SOURCE-MAP-DOMAINS.md). Public event detail and ticket controls
live in `frontend/src/features/inventory/PublicEventDetailPage.tsx` and
`frontend/src/features/events/`; staff ticketing uses `eventTicketingApi.ts` and the
`EventInvitesPanel`, `EventTicketsPanel` and `EventPromosPanel` components.
Organizer, audience and partner pickers share `features/staff/AsyncSearchPicker.tsx` through
`EventPartnerPickers.tsx`; `EventPartnersSection.tsx` is the create form's "Organizers & partners" step,
`EventAudienceOrganizations.tsx` the Settings-tab audience editor, `EventCheckInList.tsx` the Check-in
tab's live list, and `eventPartnersApi.ts` their queries/mutations. `EventAudienceOptions.tsx` owns the
one wording of the registration-audience choices used by events, series and space defaults.

[Module families and public-site settings](SOURCE-MAP-MODULE-FAMILIES.md) maps the
WP2 loan/public-site gates, compatibility splits, family dashboards and routing.
WP5 staff UX: `components/ui/ListColumns.tsx` supplies shared table column/density
controls, stored in URL list state and `operations/serializers_saved_views.py`.
`features/staff/quickCreate.ts` owns permission-filtered palette creation intents.
`features/staff/handover/HandoverWizard.tsx` and `DirectHandoverWizard.tsx` guide
phone handovers through existing workflow endpoints; `HandoverBoxScan.tsx` and
`HandoverItems.tsx` handle scoped scans and return quantities. `CameraTorch.tsx`
adds optional lighting; `QrScanner.tsx` shows continuous-scan feedback and haptics.
`admin_api/serializers_creation_setup.py` validates nested creation profile/modules
and first staff; `makerspaces/creation_setup.py` applies setup atomically and schedules
invitation delivery after commit. The console creation steps live in
`features/staff/panels/usersModals/CreationWizardSteps.tsx`.
`organizations/views_console.py` and `services_console.py` own superadmin create/link
setup alongside `views_admin.py`; `features/staff/OrganizationSetup.tsx` renders it.
`organizations/services_owner.py` owns atomic owner assignment shared by the installer, makerspace API
and `/control/`; `makerspaces/admin_owner.py` defines the add-only owner organization form and the
`MakerspaceAdmin` mixin that assigns the owner and turns a post-validation owner failure into a message.
`features/staff/panels/usersModals/OrganizationPicker.tsx` supplies the creation wizard's searchable,
paginated active-organization picker and new-organization option.
Organization-link audit IDs are inert source provenance in
`tenant_migration/audit_references_meta_ux.py`.
`features/members/memberCard/offlineLoans.ts` stores an explicit own-loan projection;
`OfflineLoansControl.tsx` owns device opt-in and `public/member-pwa/offline.js` renders
the stale snapshot. `components/ui/jobStore.ts` and `JobTray.tsx` observe async jobs
across panel navigation and fence late callbacks after account/session cleanup.

WP3 delivery timing lives in `integrations/models_timing.py`, `quiet_hours.py`,
`digests.py`, `timing_dispatch.py` and `reminders_deferred.py`; the existing F1 sweeper
owns its durable release claims. `views_timing.py` configures tenant timing and the
encrypted inbound credential; `bounce_webhooks.py` exports `views_bounce.py`, which verifies provider HMACs and writes
address-hash suppression. `notifications/models_broadcasts.py`, `broadcasts.py` and
`views_broadcasts.py` own scoped member segments, matrix fan-out and personal announcements.
`payments/failure_notifications.py` handles verified failed attempts without closing debt.
Booking models are explicitly exported from `bookings/models.py` over `models_spaces.py`,
`models_booking.py` and `models_feed.py`; `services_reschedule.py` and `services_recurrence.py`
reuse the ordinary space lock and booking policy. `views_feed.py` owns private booking ICS
tokens and `accounts/rbac_bookings.py` supplies owner-only scope through `rbac.py`.
`events/middleware.py`, `config/log_setup.py` and `frontend/nginx.conf` protect
event, booking and maintenance calendar bearer URLs from access and request logs.
The new schema policies live in `data_export/*_wp3.py` and `tenant_migration/*_wp3.py`.
Frontend controls are `bookings/BookingCalendar.tsx`, `BookingReschedule.tsx`,
`notifications/AnnouncementFeed.tsx` and the staff `BroadcastComposer.tsx` and
`NotificationTimingSettings.tsx`. See [WP3-NOTIFICATIONS-BOOKINGS.md](WP3-NOTIFICATIONS-BOOKINGS.md).

WP4 inventory and machine depth is described in [WP4-INVENTORY.md](WP4-INVENTORY.md).
Public loan terms reuse `inventory/serializers.py` and `public_terms.py`; one-shot
subscriptions live in `models_watch.py`, `views_watch.py` and `notify_me.py`, called
by the availability observer and registered with the shared F1 reminder sweeper.
Stocktake policy snapshots, blind serializers and schedules live in
`operations/models_stocktake_discipline.py`, `serializers_stocktake.py`,
`stocktake_discipline.py` and `views_stocktake_discipline.py`.
`machines/views_public_detail.py`, `serializers_public_detail.py` and
`public_detail.py` own the independent public detail/collection and aggregate ETA;
the original `machines/views_public.py` remains a separate surface.
Local materials use `models_materials.py`, `material_catalogue.py` and
`views_materials.py`; custom intake uses `intake.py` and `views_intake.py`.
Maintenance usage calculations live in `maintenance/meters.py` and `meter_jobs.py`,
with separate F1 occurrences in `reminders_meters.py`. Hashed staff ICS credentials
and live scope checks use `models_feed.py`, `calendar_feed.py` and `views_feed.py`.
The `*_wp4.py` siblings own capability, export, authority and projection additions.
Frontend controls are `inventory/NotifyWhenBack.tsx`, `MachineIntakeForm.tsx`,
`staff/panels/StocktakeDiscipline.tsx` and the material, disclosure, meter and feed
components in `staff/panels/machine/`.

Member renewal automation lives in `makerspaces/membership_renewals.py`, with the
record-first charge seam in `membership_renewal_charges.py`, F1 reminder discovery
in `membership_renewal_reminders.py` and owner-only F3 mail in
`membership_renewal_notifications.py`. `membership_plan_services.py` keeps its
explicit compatibility exports. `membership_self_service.py` owns cancel/leave;
`self_service_access.py` applies owned-membership RBAC and module/feature checks.
Account profile/session routes use `accounts/views_self_service.py`, serializers
and schemas in the matching siblings, and `web_sessions.py` for stable browser
JWT lineage over the existing token ledger. Subject export routes/jobs live in
`data_export/subject_views.py`, `subject_services.py` and `subject_tasks.py`;
`subject_selectors.py` proves row ownership while `subject_archive.py` reuses the
existing field classification. `subject_boundary.py` reuses source-gate boundaries.
Frontend account controls live in `features/members/MemberAccount*.tsx` with
`memberAccountApi.ts`; staff plan controls use `MembershipRenewalFields.tsx`.
See [member-account-renewals.md](member-account-renewals.md) for policy and limits.
Public item deep links live in `frontend/src/features/inventory/PublicItemPage.tsx`;
they reuse `inventory/views.py`'s existing `PublicInventoryDetailView` and the
catalogue's `PublicProductSerializer`. Public search builds an allowlisted vector
from name/description in that view; the staff search vector remains unchanged.
`frontend/src/components/PageMetadata.tsx` owns routed client-side head tags.
`features/members/MemberPortalTabs.tsx` owns member tab URLs and keyboard navigation;
`MemberArea.tsx` reuses the member panels with membership-gated activity and independent
payment visibility. `features/discovery/` owns URL filters, calendar rendering and
tenant-zone date boundaries (`calendarDates.ts`); `features/bookings/SpaceDiscoveryCalendar.tsx`
reads published busy intervals through the existing availability API.

Wave 5 member PWA/offline-card entry points are indexed in
`docs/SOURCE-MAP-CLIENT.md`; toast/undo, setup progress and dashboard drill-down
entry points are indexed in `docs/SOURCE-MAP-CONSOLES.md`.

Cloud surfaces: `accounts/views_social.py` explicitly exports the nonce/login views in
`views_social_login.py` and identity management in `views_social_identities.py`, with shared
verification/error helpers in `views_social_helpers.py`. `integrations/health.py` explicitly exports
`health_status.py` rollups and `health_chat.py` destination/legacy delivery summaries. The
read-only scheduler control page lives in `operations/admin_scheduling.py`.
The shared reminder foundation is `operations/models_reminders.py`,
`reminder_types.py`, `reminder_registry.py`, `reminder_services.py`, `reminder_sweeper.py` and
`tasks_reminders.py`; `membership_payment_reminders.py` registers the admission
payment-deadline consumer for F3 membership notices. Loan borrower/staff sources
are registered explicitly alongside these payment consumers. The explicit `payments.due`
consumer in `payments/reminders.py` uses durable claims for owner-only email.
Receipt and credit-note snapshots live in `payments/models_documents.py`; `documents.py`
allocates the shared tenant sequence in the settlement/refund transaction. `document_pdf.py`
renders snapshots, `document_delivery.py` owns payer-only mail and signed grants, and
`views_documents.py` rechecks payment ownership or active VIEW_FINANCE authority at download.
The finance registry is `operations/report_definitions_finance.py`; `reports_finance_sources.py`
selects dated ledger rows, `reports_finance.py` builds local-period revenue/cash summaries,
and `reports_accounting.py` builds the balanced CSV journal. `report_date_ranges.py`
distinguishes calendar filters from rolling scheduler instants. Frontend document access is
`features/payments/PaymentDocuments.tsx`, policy editing is `staff/BillingDocumentsSettings.tsx`,
and report presentation is `staff/panels/OperationsReportsFinance.tsx`.
Core due dates and billing policy live in `payments/due_dates.py`, `models_billing.py`
and `views_billing.py`; manual receipt corrections/release reuse
`services_refunds_offline.py` and `views_refunds_offline.py`.
`operations/reports_cash_book.py` owns effective manual money-in/out totals.
`payments/schemas_billing.py` documents typed business errors and DRF field-validation
responses. The module guide links into `MODULES-INVENTORY.md`, `MODULES-WORKSHOPS.md`,
`MODULES-PLATFORM.md` and `MODULES-LIFECYCLE.md` to keep each reference below the file ceiling.
Explicit lazy machine/maintenance adapters live in
`reminder_machine_sources.py`. Certification expiry and staff digests live in
`machines/reminders_certifications.py` and `reminders_certification_digest.py`;
maintenance reminders and anchor maths live in `maintenance/reminders.py` and
`recurrence.py`. `machines/models_policy.py` owns tenant/type numeric settings.
`admin_api/views_certification_types.py` and `views_certification_grants.py` own
paginated trainer rosters; `serializers_certifications.py` validates type names and
maps concurrent unique-name collisions to field errors. The member history lives in
`machines/views_member_certifications.py`; `views_machine_type_policy.py` owns policy edits.
Frontend trainer controls live in `staff/panels/machine/CertificationsPanel.tsx`,
`CertificationGrants.tsx` and `MachineReminderPolicy.tsx`; `staff/certificationsApi.ts`
owns paging. `members/MemberCertifications.tsx` owns private history and
`staff/BookableSpaceForm.tsx` owns the optional booking training link.
Staff/member API and UI behavior is described in
[machine-training-maintenance.md](machine-training-maintenance.md).
Explicit event and booking consumers live in `events/reminders.py` and
`bookings/reminders.py`, sharing requester delivery and fair batch discovery in
`operations/reminder_members.py`. The booking editor uses the paginated
`staff/staffBookingApi.ts` choices under booking authority.
Queries use `accounts/rbac.py:scope_for_scheduled_work`; see
[reminder-schedules.md](reminder-schedules.md) for UTC, claims and migration rules.
Platform monitoring uses `admin_api/views_platform_monitoring.py` and its schema sibling;
`operations/platform_dashboard.py` scopes tenants, `platform_signals.py` reads deployment state,
`platform_checks.py` declares checks, and `platform_problems.py` isolates failures.
`platform_integration_health.py` reads channels without creating settings; `tasks_platform.py`
and `scheduler_telemetry.py` own scheduled checks and beat completion telemetry.
Tenant counters and allowances are read by `makerspaces/usage_snapshot.py`.

Membership admission is described in [membership-admission.md](membership-admission.md).
`makerspaces/models_admission.py` owns the settings and immutable vouch models.
`membership_services.py` remains the explicit compatibility barrel over
`membership_helpers.py`, `membership_legacy.py` and `membership_admission.py`.
Admission settings/forms/vouches/charges live in `membership_admission_settings.py`,
`membership_admission_forms.py`, `membership_vouching.py` and
`membership_admission_payments.py`; all grants use `membership_activation.py`.
`membership_admission_direct.py` applies gates to walk-in and core creation paths.
`views_admission.py` serves the public policy and owned applicant/voucher routes;
`admin_api/views_membership_admission.py` serves manager settings. Existing staff
review serializers include answer snapshots and named vouches. Committed payment
callbacks live in `payments/admission_settlement.py`, with narrow rejoin debt access
in `payments/admission_access.py`. `operations/tasks_admissions.py` drives expiry
and settlement recovery in both schedulers. Application-export audit writes and
settlement activation take explicit tenant write boundaries; reviewer debt summaries
use the existing finance-scoped payment context.

Loan policy lives in `makerspaces/models_loan_policy.py` and `loan_policy.py`;
`admin_api/views_loan_policy.py` / `serializers_loan_policy.py` extend the existing
return-policy route. `hardware_requests/workflow.py` exports `renewal_workflow.py`
for policy-bound extensions; `renewal_views.py` serves member/staff actions.
`loan_reminders.py` and `loan_reminder_notifications.py` adapt F1 claims to borrower
mail and F3 escalation. `inventory/availability_loan_limits.py` owns borrower quantity
ceilings; `accounts/rbac_borrowers.py` scopes owned rows even without membership.
`makerspaces/member_loans.py` includes reviewed and direct loans in member activity.
See [loan-policy.md](loan-policy.md) for defaults, inheritance, gates and routes.
`tenant_migration/tenant_dump_authority_loans.py` declares portable loan terms and
renewal history; the fan-out gate registry names the legacy reminder helper that
actually holds the boundary.
Frontend loan controls are `staff/MakerspaceLoanPolicySettings.tsx`,
`staff/StaffLoanRenew.tsx` and `members/MemberLoanRenew.tsx` under features/.

The backend, frontend and domain lookup continues in [SOURCE-MAP-APPS.md](SOURCE-MAP-APPS.md).

Space packs live in `makerspaces/space_pack_*`, with their literal configuration
projection in `data_export/space_pack_configuration.py`. The profile model is
`makerspaces/models_space_packs.py`; HTTP contracts are in
`admin_api/serializers_space_packs.py` and `views_space_packs.py`.
`capabilities.py` re-exports the catalog from `capability_definitions.py` and
validation from `capability_validation.py`;
`loan_policy_settings.py` is the settings editor and pack shared policy writer.
See [SPACE-PACKS.md](SPACE-PACKS.md) for the protocol and authority boundaries.
Frontend `staff/SpacePacksPanel.tsx` owns export/preview/apply, with handwritten
`spacePacksApi.ts` calls and `SpacePackProfilePicker.tsx` for creation profiles.
Platform profile admin scoping is declared in `config/admin_scope_registry.py`;
the profile route is platform-exempt in `tenant_migration/gate_policy_http.py`,
while pack application explicitly asserts the target source gate before writes.
Backend app ownership is indexed once in [SOURCE-MAP-APPS.md](SOURCE-MAP-APPS.md);
recovery and tenant-dump internals are in [SOURCE-MAP-RECOVERY.md](SOURCE-MAP-RECOVERY.md).
`backup/restore_hooks.py` and `tenant_migration/restore_hooks.py` clear copied download
bearers during deployment restore and slice staging.

## Community and notification delivery

Public handles/profiles, GitHub/activity history, presence/TV, event speakers and booking departures/
galleries, the combined makerspace home and staff settings are indexed in
[SOURCE-MAP-COMMUNITY.md](SOURCE-MAP-COMMUNITY.md). Personal contract/provider files, domain
notification adapters and channel UI are indexed in
[SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md). These maps include concrete backend,
frontend, migration and registry siblings; INVARIANTS.md owns their rules.

## Self-host entry points

`install.sh` performs read-only host preflight and fetches a pinned temporary release before the
shared deployment questionnaire. `setup.sh` consumes confirmed private answers and starts the chosen
stack. `scripts/setup-questions.sh` owns question order/summary, `setup-question-input.sh` owns
validation and private answer transport, and `setup-write-environment.sh` writes the confirmed dotenv
and primary layer. `setup-first-run.sh` preserves existing secrets and supports a confirmed retry.
`setup-area-questions.sh` owns the shared area follow-ups; `setup-areas-json.sh` encodes their private
stdin document. `module-area-selection.sh` presents the live on/partial/off menu, while
`module-legacy-selection.sh` preserves module-key exclusion automation. Backend `makerspaces/setup_areas.py`
maps bundles to registry modules/features; `setup_area_application.py` and `setup_settings.py` apply
them atomically through audited writers via `apply_setup_areas`. `integrations/timing_settings.py`
and `machines/policy_settings.py` are shared with their existing staff editors.
`compose-deployment.sh` appends the frontend/storage overlays (and, for TLS layers, the control-plane
tunnel overlay) consistently for `spaceworks-compose.sh` and `setup-host-orchestration.sh` topology
records. Update, rollback and restore use that wrapper. `apply-settings.sh` applies the `CONTROL_PLANE_*`
keys on an installed host without changing the release (`control-plane-settings.sh`, installer option 6,
asks the questions and calls it with `--control-plane`); the opt-in route itself lives in
`deploy/control-*.caddy` and the nginx generator `frontend/docker-entrypoint.d/40-control-plane.sh`, whose
address validation (`frontend/docker/control-plane-allowlist.sh`) the questionnaire shares.

`compose-deployment.sh` also selects the running app, writer, image, rollback and one-shot service sets.
`update-rollback.sh` restores previous application images only, without rerunning migrations or replacing
the database. `install-runner.sh` optionally registers the install-owner GitHub Actions systemd service
and prints required repository/security settings; `runner-release.py` verifies its release asset checksum.
The release workflow deploys an exact published main version through the installed updater.

Lane E printable credentials: `operations/printable_layout.py`, `printable_serializers.py`,
`printable_fonts.py` and `printable_pdf.py` are always-present geometry/font/overflow/PDF
mechanisms with no domain imports. `events/badge_templates.py` validates event fields and
converts v1 layouts; `badge_rendering.py` adapts authorized values. Certificate design is
owned by `models_certificate_templates.py`, `certificate_templates.py`,
`services_certificate_templates.py`, `certificate_artwork_storage.py`,
`serializers_certificate_templates.py`, `views_certificate_templates.py` and
`urls_credentials.py`; `services_certificates.py` freezes issuance and
`certificate_rendering.py` consumes its snapshot; `certificate_rendering_legacy.py`
preserves pre-designer PDF bytes for rows with empty migration snapshots.
`backup/object_reference_certificates.py`
registers artwork keys embedded in issuance JSON; the normal retention/purge registries
also include concrete artwork and revision rows. Frontend shared design controls live in
`components/print-layout/`; `EventCertificateDesigner.tsx` and
`eventsCertificateDesignerApi.ts` own event draft/revision/upload/preview state.

Account contexts live in `accounts/models_user.py` (re-exported by `models.py`),
`account_constraints.py`, `account_kind_guards.py` and `managers.py`.
`staff_accounts.py` atomically creates a tenant staff principal and its roles/type scopes;
`membership_context.py` shares the object/SQL account-validity rules used by RBAC.
`backup/main_projection_catalog.py` owns the physical-table check re-exported by
`main_projection_registry.py`; the staff inert-shell boundary is declared there, with
projection and guarded reversal reserved for account-split P4. Demo account/machine
fixtures are split into `inventory/management/commands/_seed_demo_fixtures.py`.
