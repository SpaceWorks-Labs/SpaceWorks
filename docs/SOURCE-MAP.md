# SpaceWorks source map

> **This is the file-layout half of `CLAUDE.md` / `AGENTS.md`.** It was split out when that file crossed
> the harness's memory-file size limit; nothing was dropped in the move. It has no `AGENTS.md`-style twin —
> both names of that document point at this one path, so edit it in place.
>
> Paths drift. If this disagrees with the tree, the tree wins — fix this file in the same commit.

## Current source map (real paths)

Canonical personal delivery is the envelope/configuration/provider pipeline indexed in
[SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md). SMS, Twilio/Meta WhatsApp,
physical sender/STOP protection, device children and canonical reports are reconciled there.
Addressed enqueue/worker compatibility shims are inert; legacy schema and historical import
helpers remain for replay pending the independent
[retirement and activation checkpoints](notification-reconciliation-rollout.md).

The [Events programme map](SOURCE-MAP-EVENTS-PROGRAMME.md) covers application/team,
upload/retention, contributor/Mentor Desk, judging/gallery, credential/certificate,
form/Saved details and runtime/retention adapters at `f1ef7736`. It includes incomplete
provider installation explicitly; see the [closure ledger](events/integration-status.md)
before interpreting a mounted route as an enabled/accepted workflow.

Public-image POST/PUT presigns live in `inventory/public_image_storage.py` and
`bookings/storage.py`; both delegate bounded validation and conditional, write-once promotion
to `inventory/public_image_promotion.py`. Membership owner mail is classified as staff/account
or community in `makerspaces/notifications_p2_members.py`; `operations/notifications_p2.py`
keeps the owner route separate from the existing staff-summary category.
Member-account comeback lives in `accounts/account_restore.py` (locked eligibility and identity-only
reactivation), `account_restore_email.py` (reset-queue restore links), `account_restore_phone.py`
(phone login-start restore OTPs), and `account_restore_social.py` / `account_restore_social_device.py`
(fresh existing provider proofs). `recovery_locks.py` owns User-before-envelope proof locking.
`models_account_restore.py` stores single-use provider intents; `views_account_restore.py` and
`serializers_account_restore.py` expose their anonymous, throttled confirmation contracts.
The web restore-link landing page is `features/auth/AccountRestorePage.tsx`.

Member-account deletion Stage B lives in `accounts/account_purge.py` (tenant orchestration and
global identity finalization), `account_purge_scrub.py` (mutable tenant copies), and
`account_purge_objects.py` (committed object deletion followed by quota release).
`models_account_purge.py` defines tenant progress, object cleanup and Apple credential/
revocation work. `apple_credentials.py` exchanges sign-in authorization codes;
`apple_revocation.py` retries revocation from the Stage A on-commit task and daily sweep.
`models_email.py` holds the email-challenge/counter classes re-exported by `models.py`.
The member account page composes `MemberAccountDeletion.tsx`,
`AccountDeletionReauthentication.tsx`, `AccountDeletionBlockers.tsx` and the session-keyed
TanStack Query hooks in `accountDeletionApi.ts`. Privacy disclosure is in
`docs/privacy-account-deletion.md`.
Mobile analytics prerequisites (1f-1): `accounts/models_activity.py` owns grant/day and
anonymous attestation outcomes; `device_activity.py` records validated authentication
activity. `accounts/authentication_device.py` validates native grants and locks User before
DeviceGrant for the revocation-safe heartbeat used by `authentication.py`.
`integrations/models_tracking.py` owns staff push attempts, anonymous SMS
outcomes and tenant-bound bounce replay identities. Staff delivery uses `push.py`; member
delivery uses `notifications/member_push.py`, `envelope_push_leases.py` and
`envelope_push_transport.py` beneath the canonical envelope delivery. The older lease helpers
remain for retained legacy staff matrix legs.
`integrations/email.py` stamps connection provenance, `dispatch_delivery.py` retains
provider IDs and `views_bounce.py` handles exact correlation and replay protection.

Addressed template values share domain adapters without importing the optional inbox:
`payments/notification_projections.py` owns audience-specific payment bags and local due
dates; `machines/service_printing_projection.py` owns the kernel-to-printing projection
(including capability quantity and printing status). Payment and printing notification
adapters pass reviewed scalar projections into canonical envelopes.
`hardware_requests/notification_projection.py` supplies the source-backed audience projection;
legacy `integrations/messaging/sources.py` remains a compatibility seam, not another outbox.

`machines/models_tracking.py`, `status_tracking.py` and `consumable_costs.py` own immutable
status/cost facts. `service_manual_usage.py` contains typed manual logging behind the
`service_consumable_pools.py` compatibility wrapper; `usage_attribution.py` validates
optional local members/times. `inventory/cost_basis.py` validates current price units for
products and pools. `admin_api/views_machine_usage_candidates.py` and the React
`panels/machine/UsageAttributionFields.tsx` provide the scoped optional member picker.

Machine analytics (1f-2 area C) register in `operations/report_definitions_machines.py`.
`reports_machine_common.py` resolves staff authority/type scope, `reports_machine_facts.py`
projects allowlisted source facts, and the usage/heatmap/downtime/service/maintenance/queue/health
builders own their measurements. `org_machine_reports.py` combines partitioned numeric inputs;
`org_machine_report_schemas.py` declares organization schema parity. Typed API rows live in
`serializers_reports_machine_analytics.py`. The field and measurement handoff is
`docs/report-machines-1f2.md`; focused tests are `backend/tests/analytics/test_c_*_m1f2.py`.

Role dashboards (1f-4): `operations/dashboard_widgets.py` declares and gates report-backed
widgets, while `dashboard_counts.py` preserves the legacy count contract and
`dashboard_handover.py` serves queue-only handover homes. `serializers_dashboard.py`
describes the additive widget/chart and queue payload. `org_report_charts.py` projects
existing strategy-backed organization charts onto combined fields; `org_reports.py`
keeps combined data inseparable from its tenant breakdown.
Personal usage lives beside member activity: `makerspaces/member_usage_views.py` owns
the membership-versus-core-payments boundary at `/member/makerspaces/<id>/my-usage`,
`member_usage_service.py` owns authenticated-user-only facts, and
`member_usage_serializers.py` documents the summary/chart response. Claim policy is in
`accounts/claim_routes_member.py`. Tests: `analytics/test_dashboards_m1f4.py`,
`test_my_usage_m1f4.py` and `test_dashboard_native_org_m1f4.py`.

`inventory/models_tracking.py` defines stock observations; `availability_stock.observe_stock`
reads authoritative quantity buckets, while `stock_snapshots.py` gates tenant fan-out and
`tasks.py` exposes the daily task. `data_export/classification_m1f1.py` classifies new facts;
`subject_runtime.py` provides the separate personal runtime allowlist, consumed by
`subject_archive.py`. Tenant imports remap cost sources in `semantic_remap.py` using
`tracking_references.py`; `verification_semantic.py` verifies non-FK references behind
the existing `verification.py` exports. Regression coverage is `backend/tests/analytics/`.

Frontend analytics (1f-5) lives in `features/staff/panels/`: `reportAreas.ts` groups only
server-catalog entries into nine areas, `ReportAreaSections.tsx` mounts the selected
report query, and `AnalyticsData.tsx` pairs charts with complete source-table toggles
(including rows omitted by chart axes or top-N display). `analyticsApi.ts` imports the
generated serializer types and owns scoped query keys under the existing `operations-report`
invalidation prefix, and matrix-to-record projection. `charts/wireChartSpec.ts` adapts
the backend F1 spec into the existing accessible chart kit, preserving tenant, currency,
measurement-unit and negative-value rules. Null specs retain the table presentation.
`DashboardAnalyticsWidgets.tsx` renders server-authorized widget kinds and the separate
handover queue home; `staffAccess.ts` and the flat sidebar admit that queue-only home.
`ModuleAnalytics.tsx` embeds catalog-authorized small panels in inventory, machines,
bookings, events, membership, money, communications and device consoles. The online
payment rail is not a gate on core money analytics.

`features/members/memberUsageApi.ts` and `MemberUsagePanel.tsx` own the personal
`my-usage` query, keyed by makerspace under `member`, and its charts in the member
overview. They suppress 403/404 and display payments independently of membership usage.
`organizationAnalyticsApi.ts`, `organizationReportChoices.ts` and
`panels/OrganizationAnalyticsPanel.tsx` retain the server's combined total alongside
every makerspace breakdown, with period/grain controls and nullable combined chart specs.
`platformAnalyticsApi.ts`, `PlatformAnalyticsPanels.tsx` and `PlatformAnalyticsPicker.tsx`
add services/usage charts and paginated tenant drill-down to `PlatformDashboardPanel`.
Hidden service buckets have one anonymous label and no tenant identifiers; scoped
catalog/report 403s remain explicit blocks. The two platform fallback specs mirror the
registry for cached responses predating chart metadata; current platform responses include
the canonical `chart_spec`. Report, dashboard, member, organization and picker contracts
now import `frontend/src/generated/api.ts`; widget JSON is projected at the chart boundary.
Vitest panel suites live beside these components, with registry fixtures and shared
fetch/provider helpers in `src/test/reportChartCases.ts` and `analyticsFixtures.tsx`.

Personal channel UI is consolidated in `features/notifications/`: `channelsApi.ts`,
`channelCatalog.ts`, `ChannelSetupPanel/Form`, `WhatsAppTemplatesEditor`, `ChannelTestSend`
and `ChannelDeliveryLog` own canonical configuration, approval, diagnostics and history.
`PersonalChannels`, `ChannelPreferences`, `MyNotificationSettings` and `SmsConsent` own
connections, category selections and current phone/sender-bound consent. `smsConsentApi.ts`
uses the retained core consent endpoints. `features/messaging/MessagingFeedback.tsx` supplies
shared inline feedback. The old messagingApi, MakerspaceMessagingSettings, MessagingTestSend,
WhatsAppTemplateBindings/BindingForm and MemberMessaging components are deleted.
`MemberArea.tsx` exposes Channels to server-authorized account-only owners independently of
membership/inbox; old messaging section links remain aliases. Staff have a core My channels tab;
platform navigation remains separate. Query keys bind account, context and tenant; session
switches clear private caches and late mutation results cannot populate another account.
`MemberPhoneVerification.tsx` refreshes consent reads after linking without subscribing anyone.

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
`SpaceWorks-Labs/SpaceWorks-Design` repository for use as a submodule.

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

Event uploads, website copy-on-write and duplication use
`makerspaces/event_asset_transaction.py` to reserve keys/quota, release all domain row
locks for `event_asset_work.py` storage operations, then revalidate and commit the complete
graph. `events/website_copy_snapshot.py` freezes relational copy inputs across that gap.
`makerspaces/website_asset_journal.py` owns the durable cleanup-intent/write-claim fence
and exactly-once attachment charge. `resource_clone.py` retains the existing Bookings
transaction and the shared compensation helper; event callers use its phased subclass.
Before that engine runs, `events/website_preparation.py` (`prepared_page_write`) and
`events/clone_preparation.py` re-read the actor, declare and prepare the tenant/event scope
outside any domain transaction and pre-allocate the EventPage ID, which the engine reuses on
both passes (`event_asset_transaction(page_id=...)`). Inside, `services_write_boundary.event_write`
takes the fences and locks, `prepared_copies` refuses a page that changed since preparation,
and duplication adds the fenced programme and design copy steps (decision #86, 2026-10-23).

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

Booking/event analytics (1f-2 D/E): `operations/report_definitions_de.py` registers
the new builders and organization combiners; `report_fields_de.py` owns their allowlists.
`reports_booking_trends.py` provides booking-utilization v2; `reports_booking_analytics.py`
owns occupancy, lead-time and member rankings. `reports_event_analytics.py`,
`reports_event_revenue.py` and `reports_event_quality.py` own signup/funnel, money,
and check-in/feedback measures respectively. `org_report_de.py` combines count/sum/rate
inputs. Measurement boundaries and per-key fields are in `docs/report-builders-de.md`.

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
Settings authority (L17, #101): `makerspaces/settings_authority.py` is the one write gate
(`assert_setting_write`, `decide`, `record_change`); `settings_authority_registry.py` holds the
module → manager-action map, finance prefixes, the rental-timing fixed exception and the
rows-only extension tuples; `settings_authority_writes.py` writes grants and locks,
`settings_authority_effective.py` answers "what may I edit", `settings_authority_views.py` is the
staff API and `models_settings_authority.py` the append-only grant/lock rows.
`domain_settings.py` and `loan_policy_settings.py` are adapters on it. Folded capabilities (#97):
`capability_definitions_r2_l17.py` defines the per-parent keys, `folded_capabilities.py` the 404
gates and the To-Buy kind / warranty host mapping, `capability_purge.py` +
`capability_purge_plans.py` + `admin_capability_purge.py` the superadmin purge, and
`module_switch_authority.py` who may install a module (#128 C-10). Report sources that are
capabilities resolve in `operations/report_sources.py`. Frontend: `features/staff/
SettingsAuthorityCard.tsx`, `SettingLock.tsx` and `settingsAuthorityApi.ts`.
Fixed membership roles live in `makerspaces/role_catalog.py`. `accounts/rbac_roles.py`
shares the valid-role predicate between object resolution and SQL `Exists` filters;
`makerspaces/role_membership_writes.py` is the complete-set writer used by lifecycle
and staff assignment services. Machine authority links are per membership and type in
`machines/models_membership_scope.py`, resolved by `role_scope_resolution.py` and
written by `member_scope_services.py`. The console API lives in
`admin_api/views_member_scope.py` and `serializers_member_scope.py`.
Frontend `features/staff/panels/RoleSetPicker.tsx` owns exclusive/combinable checkbox selection;
`roleSets.ts` owns assignment ceilings, handwritten membership role-set types and cache invalidation.
`RolesReference.tsx` renders the read-only server role catalogue. `MemberRolesControl.tsx` retains the compatibility role control; the backend refuses
member-to-staff assignment; `MemberMachineTypes.tsx` edits per-person type scope using `rolesApi.ts`.
The staffAccounts panel reuses the picker; UsersTable and MembersPanel display the whole role set.
Built-in staff assignments use separate staff accounts, never the member roster.
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
`hosting_requests/` owns managed-platform hosting requests: `workflow.py` is the only writer of
`HostingRequest.status`, `authority.py` decides who may invite and when "Join <organization>" is offered,
`retention.py`/`tasks.py` run the daily 48-hour delete and 90-day redaction, `notifications.py` sends the
platform mail, `prefill.py` builds the pre-filled `/control/` add link, and `admin.py` is the `/control/`
review (accept/reject actions and the re-auth-safe "Create makerspace" view). `makerspaces/admin_owner.py`
records the link through the add form's hidden `hosting_request` field. Frontend: `features/hosting/`
(`/hosting`, `/hosting/invite`, `/hosting/request`, `hostingApi.ts`) and
`features/staff/HostingInvitations.tsx` (the makerspace-settings and organization "Invite a makerspace"
section).
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
encrypted inbound credential; `bounce_webhooks.py` exports `views_bounce.py`, which verifies provider HMACs; both its
routes write the canonical bounce/complaint record and address-hash suppression through
`email_provider_events.record_provider_event`. `notifications/models_broadcasts.py`, `broadcasts.py` and
`views_broadcasts.py` own scoped member segments, matrix fan-out and personal announcements.
`notifications/models_push.py` owns canonical per-device children; `member_push.py`,
`member_push_policy.py`, `envelope_push_leases.py` and `envelope_push_transport.py` separate
registered fan-out, current source/device gates, fenced claims and transport. The old
member_push_leases helper remains for legacy staff matrix use. `notifications/tasks.py`
re-enters canonical envelope delivery for five-minute recovery; old enqueue IDs are inert.
`notifications/inbox_scope.py` validates persisted requester-selection subjects.
`integrations/push.py` shares one-device provider sending; `push_payload.py` builds v2
data through the existing `mobile_link_contract.py` routing contract.
`payments/failure_notifications.py` handles verified failed attempts without closing debt.
`payments/services_mobile.py` coordinates native rail locks and vendor dispatch;
`services_mobile_razorpay.py` validates and recovers native Orders through
`providers/razorpay.py`. `serializers_mobile.py` defines the vendor-discriminated response.
`terminal_settlement.py` retains late-capture refund anchors and deduplicates excess-collection
audits; `reconciliation_rail.py` closes native Razorpay Orders locally without cancelling links.
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
`public_detail.py` own the independent public detail/collection; its opt-in `queue`
summary now comes from the shared queue simulator (one snapshot per page);
the original `machines/views_public.py` remains a separate surface.

Machine-service queue ETA, notices and cancellation (decisions 44/45, every machine type):
`machines/service_queue_eta_core.py` (pure simulator: `Timeline`, `lane_summary`) and
`service_queue_eta_records.py` (records, reason vocabulary, 5-minute boundary rounding);
`service_queue_eta.py` is the ORM adapter (`queue_snapshot_for`, `machine_queue_summaries_for`,
at most four SELECTs per tenant snapshot, scalar columns only) and
`service_queue_eta_serializers.py` the shared `ServiceRequestEtaSerializer` /
`MachineQueueSummarySerializer`. `service_queue_position.py` keeps the legacy counts on one
batched ranking. Requester milestone intents live in `service_queue_notices.py`
(`reserve_milestone`, `reevaluate_head`) with delivery checks/rendering in
`notifications_p2_service_notices.py`, wired under the one `machines.service` source kind.
`service_workflow_cancel.py` owns `cancel()` (re-exported by `service_workflow`), and
`service_workflow_start.py` owns `start()` (re-exported by `service_workflow_actions`);
`service_manual_usage.py` owns linked/unlinked typed manual usage (re-exported by
`service_consumable_pools`). Public token status for any type: `public_service_status.py` +
`views_public_service_status.py`; owner member-surface routes: `views_service_cancel.py`;
staff cancel: `admin_api/views_machine_service_actions.MachineServiceCancelView`. Member
dashboard rows: `makerspaces/member_activity_machine_service.py`. Frontend:
`frontend/src/features/machine-service/` (`ServiceRequestEta`, `QueueSummary`,
`ServiceCancelButton`, `OwnerCancel`, `MemberServiceRequestRows`,
`PublicMachineServiceStatusPage` at `/machine-service/requests/:publicToken`), with staff
row helpers in `features/staff/panels/machine/ServiceEtaLine.tsx`.
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
`features/auth/SignOutEverywhere.tsx` calls account-wide logout from member Security
and all account MFA settings, independently of membership self-service.
See [member-account-renewals.md](member-account-renewals.md) for policy and limits.

Member-account deletion lives in the `accounts/account_deletion*` service modules
and `accounts/views_account_deletion.py` / `serializers_account_deletion.py`. Stage A archives identity,
revokes session authority and coordinates existing membership/application services.
`organizations/services_governance.py:self_departure` owns organization departure
without requiring governance authority, while preserving the last-governor invariant.
`accounts/reauthentication*.py` supplies browser/device proof and provider second-factor
intents independently of the deletion transaction. Stage B purge uses the durable
tenant/object journals described above.
`accounts/account_obligations.py` locks the obligation owner after domain locks;
new loans, bookings, registrations, service jobs and membership purchases use it
to serialize against departure. Refresh rotation locks the account before tokens.
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
verification/error helpers in `views_social_helpers.py`. `accounts/services_device_grants.py`
owns shared first-grant creation for social and phone sign-in; `services_phone_device.py`
consumes the OTP-bound attestation and carries member-only phone provenance through MFA.
`makerspaces/config_native.py` owns native provider/version discovery and its OpenAPI serializers.
`integrations/health.py` explicitly exports
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
Refund cases: `payments/models_refund_cases.py` (RefundCase, RefundPolicy),
`refund_policy.py` (the due arithmetic) with `refund_policy_membership.py` (term bands, the
covered-term rule), `refund_cancellation.cancel_or_hold`/`hold_settled` (the cancel seams
events, bookings and `membership_plan_services.cancel_term` call), `services_refund_cases.py` (open/upgrade/request/
withdraw/void), `services_refund_decisions.py` (approve/decline, the only path to a
Refund), `refund_case_access.py` (queue scoping), `refund_case_sweeper.py` (hourly
rebuild), `notifications_refund_cases.py`, and the views `views_refund_cases.py`,
`views_refund_policies.py` (with `serializers_refund_policies.py`), `views_refund_member.py`. `services_refunds.open_refund_locked`
is the shared step-1 for a caller already holding the Payment lock. The report is
`operations/reports_refunds.py`. Frontend: `features/staff/refunds/` (queue, decision
dialog, policy panel with `RefundPolicyCard` and per-plan `RefundMembershipPolicies`), `staff/RefundReceiptFields.tsx` (shared receipt inputs) and
`members/MemberRefundRequest.tsx`.
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

Report infrastructure: `operations/report_registry.py` composes `report_definitions_<area>.py`;
`report_validation.py` validates privacy flags and chart specs (also a Django check),
`report_output.py` projects public rows, and `platform_scope.py` separates platform context
and service buckets from tenant authority. Organization builders register combine functions
with `org_report_aggregate.register_combine`; `report_coverage_contract.py` is the phase-1f
module-to-report acceptance table, separate from runtime prerequisites.
`report_charts_remaining.py` supplies the F1 specs for legacy and subject-detail reports,
including currency-separated ledger/journal summaries. Detail builders expose a numeric
count per row where no measurement existed; health rows retain their tenant chart axis.
`tests/operations/test_chart_spec_complete_m1f6.py` guards the whole previewable registry
and both platform analytics responses. The latter use `PlatformAnalyticsReportSerializer`.

H/I analytics register in `operations/report_definitions_hi.py`: communications v3 stays in
`integrations/reports_communications.py`; tenant mobile counts live in
`operations/reports_mobile_devices.py` and `reports_mobile_auth.py`. Their shared allowlists
are `report_fields_hi.py`; `reports_mobile_platform.py` exposes context-guarded global source
projections for platform builders. Measurement and disclosure notes: [report-builders-hi.md](report-builders-hi.md).
Area J analytics: `operations/report_definitions_j.py` registers device, presence,
audit, organization membership and delivery-health reports; `report_fields_j.py`
declares their public schemas. `reports_j_*` builds tenant rows and `org_reports_j.py`
combines organization counts and rate inputs. Person rankings and local hour-of-week
are separate tenant-only keys. Organization membership is offered only on organization
and deployment surfaces. `reports_platform_services.py` owns provider metering and the
anonymous hidden-service bucket; `reports_platform_usage.py` owns visible-space activity,
with finalized consumable sources in `reports_platform_consumables.py`.
`views_platform_analytics.py` serves the two platform keys and the action-scoped tenant
picker. `metrics_push.py` reads both per-device outcome ledgers for Prometheus.
Field/measurement contracts and the complete lane handoff are in `report-builders-j.md`.

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

Native mobile integration setup: `accounts/native_app_identity.py` owns global registration eligibility,
identity normalization and production minimum-version comparison. `mobile_associations.py` builds
  public documents using the unchanged `integrations/mobile_link_contract.py`;
  `views_mobile_associations.py` enforces frontend-host eligibility. `mobile_readiness.py` is the one
  read-only report builder used by `views_mobile_readiness.py` and `admin_native_apps.py`;
  `forms_native_apps.py` validates registration edits. Operator setup: `docs/mobile-integration.md`.

### Release 2 L2 (communications, analytics, programme closures)

- `events/programme/broadcast_{designs,placeholders,tallies,draft,views_extra}.py` -- six brand
  designs, the placeholder context, counts-only tallies, draft autosave, send/tallies/templates
  routes; `integrations/broadcasts_templates.py` holds the 13 starter templates.
- `events/approval_digest.py`, `events/notices_r2_l2.py` -- organiser digest; removal notice,
  ticket re-send, join link in confirmations. `events/reminders.py::fresh_signup` (12 h skip).
- `events/programme/analytics_{extras,org,views,serializers}.py` -- per-event extras and k>=10
  organisation insights (read by `operations/platform_insights.py`).
- `events/mentoring/chat_alerts.py`, `views_chat_alerts.py` -- room alerts and the room picker.
- `events/submissions/integrity_{jobs,http}.py`, `views_integrity.py`, `storage_reconcile.py`,
  `storage_cleanup.record_receipts` -- GitHub flag job, receipts and reconciliation.
- `events/feedback_modes.py` -- certificate / anonymous / identified feedback.
- `events/models_r2_l2.py` -- integrity checks, storage receipts, mentor alert routes.
- `integrations/{org_sender,org_sender_views,invite_chat,destination_health}.py`,
  `integrations/models_org_sender.py`.
- `notifications/{views_inbox_snooze,browser_alerts,browser_alert_crypto,views_browser_alerts,
  escalation,models_browser_alerts}.py`; `frontend/public/browser-alerts-sw.js`.
- `hosting_requests/workflow.py::request_changes|resubmit`, `HostingRequestRevision`.
- Frontend: `features/staff/eventProgramme/{BroadcastTemplateGallery,BroadcastDesignPicker,
  BroadcastUndoBar,BroadcastTalliesRow,EventAnalyticsExtras}.tsx`, `broadcastAutosave.ts`,
  `staff/hackathonJudging/IntegrityFlag.tsx`, `staff/mentorDesk/MentorAlertRooms.tsx`,
  `hosting/HostingResubmitFlow.tsx`, `notifications/{InboxRowActions,BrowserAlertsToggle}.tsx`,
  `staff/OrganizationEmailSender.tsx`.

### Release 2 L4 (membership lifecycle)

- `makerspaces/financial_year.py` -- the ONE financial-year helper (`fy_bounds`, `fy_label`, fixed
  signatures L5 reads); `admin_api/views_financial_year.py` (a finance setting via `settings_authority`).
- `makerspaces/models_membership_{rules,terms,records,privacy,invites,imports,summary}.py` -- plan/term
  vocabularies, `MembershipTerm` + append-only `MembershipTermStatusEvent`, record/titles, consent and
  erasure, invite links, imported members, summary opt-outs. `capability_definitions_r2_l4.py` (14 keys),
  `membership_features.py` (404 gates).
- Services: `membership_plan_{types,policy}.py`, `membership_term_history.py`, `membership_number.py`,
  `membership_renewal_desk.py`, `membership_{records,titles,consent,erasure,summary}.py`,
  `membership_history_timeline.py`, `membership_invite_links.py`, `membership_admission_{plans,bulk}.py`,
  `membership_import_accept.py`, `membership_admission_settings_l4.py`, `membership_refund_suggestion.py`,
  `notifications_l4.py`, `public_page_plans.py`, `views_public_plans.py`, `views_membership_member_l4.py`.
- Staff API: `admin_api/urls_membership_lifecycle.py` -> `views_membership_{desk,records,erasure_import,
  plan_archive,refunds,register,summary}.py`; import planning/apply in `bulk_import_members{,_apply}.py`.
- Refunds: `payments/refund_policy_membership.py` (FY/fixed pro rata, lifetime band, `term_for_payment`),
  `payments/refund_membership_term.py` (X21 term end after approval commits).
- Reports: `operations/reports_membership_l4_{terms,lists}.py`, `reports_membership_summary.py`,
  `report_definitions_membership_l4.py`.
- Classification: `data_export/classification_r2_l4.py`, `tenant_migration/{catalog,audit_references}_r2_l4.py`,
  `encryption/registry_r2_l4.py`, `audit/presentation_catalog_r2_l4.py`.
- Frontend: `features/staff/membershipLifecycle/*`, `memberImport/*`, `MembershipPlanRulesFields.tsx`,
  `MembershipAdmissionExtras.tsx`, `refunds/MembershipRefundExtras.tsx`, `members/{MemberAccountLifecycle,
  AdmissionJoinWithPlans}.tsx`, `members/joinPlansApi.ts`, `publicPages/PublicPlanCards.tsx`.

## Domain and frontend map
See [SOURCE-MAP-DOMAINS.md](SOURCE-MAP-DOMAINS.md) for hardware loans, payments,
printing, events, the frontend directories and connected device monitoring.
See also [SOURCE-MAP-CLIENT.md](SOURCE-MAP-CLIENT.md) for the standalone
frontend directory and browser/kiosk flow map.
See [SOURCE-MAP-CONSOLES.md](SOURCE-MAP-CONSOLES.md) for staff lists, saved views,
command-palette discovery and the connected-device console map.
Staff list preferences live in `operations/models_saved_views.py`, `serializers_saved_views.py` and
`views_saved_views.py`; cross-entity discovery is `admin_api/search.py`. Shared pagination/ordering
and entity authority live in `admin_api/list_options.py` and `staff_list_scope.py`.
Saved-view audit targets travel as inert source provenance in
`tenant_migration/audit_references_targets.py`, including after a preference is deleted.
Booking/event `views_admin_spaces.py` / `views_admin_events.py` barrels re-export the corresponding `*_list/detail.py` handlers.

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
`account_constraints.py`, `account_kind_guards.py` and `managers.py`. One account per person
(release 2, U-A1): `accounts/staff_identity.py` is the single identity seam (person / platform /
shell predicates, `has_staff_role`, `actor_ids_for`, `require_staff_mfa`);
`makerspaces/membership_managers.py` holds the fail-closed track managers behind
`MakerspaceMembership.objects` (community), `staff_tracks` and the reserved `all_tracks`;
`makerspaces/staff_role_grants.py` grants staff roles to an existing person.
`accounts/models_account_merge.py` holds `AccountMergeRecord`/`AccountMergeIntent`;
`accounts/merge_registry.py` (+ `merge_registry_types.py`, `merge_registry_rows_*.py`) classifies
every `accounts.User` reference for merges, checked by `accounts.E003` in `checks.py`.
`accounts/unification_plan.py` computes the conversion plan and its `plan_sha256` for
`management/commands/account_unification_report.py` (+ `unification_report_context.py`) and
the frozen conversion in `accounts/migrations/_0050_conversion.py`; the unified triggers are
frozen in `_0049_unified_guards.py`, the track triggers in `makerspaces/migrations/0114_membership_track.py`.
`staff_accounts.py` atomically creates a tenant staff principal and its roles/type scopes;
`staff_account_policy.py`, `staff_account_services.py` and `staff_account_lifecycle.py`
own staff lifecycle authority, onboarding, deactivation and administrator password issue.
`admin_api/views_staff_accounts.py` exposes that lifecycle; the account and makerspace
`admin_staff_*` modules reuse it in `/control/`. `accounts/admin_native.py` holds native-app administration.
`membership_context.py` shares the object/SQL account-validity rules used by RBAC.
`backup/main_projection_catalog.py` owns the physical-table check re-exported by
`main_projection_registry.py`; the staff inert-shell boundary is declared there, with
projection in `backup/staff_shells.py` and guarded reversal in `staff_shell_fences.py`,
`staff_reconstruction.py`, `main_projection_inverse.py` and `slice_merge_*`. Demo account/machine
fixtures are split into `inventory/management/commands/_seed_demo_fixtures.py`.

Account-kind authentication is enforced in `accounts/login_context.py`, `surface_policy.py`,
`authentication.py` and `tokens.py`; `session_context.py`/`auth_cookies.py` select refresh contexts.
`delegated_routes.py` exposes the authority-source classification in `delegated_route_catalog.py`;
`checks.py` fails unclassified staff URLs. `member_identity.py` and `account_kind_guards.py`
keep member credential/community writers separate. `credential_revocation.py` and
`credential_revocation_helpers.py` own generation fencing and account-owned credential teardown.
`models_password_reset.py`, `services_password_reset.py`, `services_password_reset_confirmation.py`,
`services_password_reset_drain.py` and `password_reset_crypto.py` bind recovery to the exact account
and member/staff/platform context. `password_reset_context.py` owns trusted-origin/live-tenant policy
and reset-page destinations; `credential_locks.py` enforces the shared credential-operation lock order. `services_staff_invitations.py`,
`staff_invitation_acceptance.py` and `staff_invitation_delivery.py` own initial staff password setup.
`admin_api/urls_staff_accounts.py` and `serializers_staff_accounts.py` define its HTTP contract;
`accounts/admin_staff_lifecycle.py` and `makerspaces/admin_staff_accounts.py` provide control actions.

Staff transport is in `tenant_migration/portable_staff.py`, `tenant_dump_staff.py`,
`tenant_dump_user_closure.py`, `staff_postconditions.py` and `catalog_account_context.py`;
`data_export/runner_users.py` and `subject_selectors.py` include tenant staff without retired shells.
`makerspaces/staff_retirement.py` performs the purge retirement step from `lifecycle_purge.py`.
`makerspaces/lifecycle_purge_graph.py` owns the ordered whole-tenant deletion graph.
`admin_governance.py` and `admin_lifecycle_review.py` provide the slim hidden-tenant lifecycle list
and pending archive-request review; ordinary tenant object pages remain scoped.
Shared chat destination facts use `integrations/notification_destination_events.py`;
`notification_proofs.py` keeps proof and unlink account-bound. Transport/backup policy:
[account-split-portability.md](account-split-portability.md).

Frontend `lib/api/sessionContext.ts` selects member, staff:<slug> or platform;
`sessionTokens.ts`, `client.ts`, `requests.ts` and `reauthentication.ts` isolate tokens, refresh
and late responses. `lib/SessionBoundary.tsx` and `lib/queryClient.ts` partition server-state
caches. `features/staff/useStaffSession.ts` restores tenant or delegated-member workspaces;
`LoginPanel.tsx` and `ChangePasswordGate.tsx` handle tenant passwords and mandatory change.
`features/staff/panels/staffAccounts/` owns creation, roles/scope, status and password dialogs,
using the handwritten contract in `lib/api/staffAccounts.ts`. Password secrets remain in mounted
dialog state, outside Query caches/storage. Staff offline rosters, jobs and toasts are context-bound;
member offline cards/loans retain their separate lifecycle. Tests: `backend/tests/account_split/`
and frontend `*.accountSplit.test.*`, `sessionContexts.test.ts`, `contextStores.test.ts`.

Addressed messaging is part of core integrations, not a second delivery pipeline.
`models_endpoints.py` owns canonical channel configuration and templates; `models_contract.py`
owns personal envelopes/deliveries; `models_cutover.py` owns `NotificationCutover`, encrypted
`NotificationIngress`, `NotificationLegacyMapping`, credential versions and provider references.
`models_messaging_consent.py` retains append-only consent and shared physical suppression,
alias/correlation protection. Platform sender settings and sender identity/history remain in
`models_messaging_settings.py`; its old tenant settings/binding models and the old
`models_messaging_delivery.py` send records survive only for conversion/import compatibility.

`notification_sender.py` owns canonical own/platform resolution, sender snapshots and retired
verifiers; `notification_addressed.py` rechecks addressed eligibility, SMS routing snapshots,
segments and WhatsApp correlation before provider I/O. `messaging/ties.py`, `consent.py`,
`protections.py`, `stops.py`, `correlation.py`, `segments.py` and reviewed `projections.py`
provide the ported safeguards. `recipients_addressed.py` / `recipients_owners.py` share source
recipient extraction without requiring inbox installation. `notification_personal_policy.py`
keeps opt-outs effective even when the optional inbox app is absent. OTP remains in `sms/`.

`notification_ingress.py`, `notification_ingress_apply.py`, `notification_legacy_ingress.py`,
`notification_callbacks.py` and provider ingress modules authenticate/journal/replay callbacks.
The old messaging webhook URLs remain signed compatibility ingress, not send authority.
`notification_cutover.py` and `management/commands/notification_cutover.py` own barrier, route,
replay, verify and activate. Integrations 0041 expands; 0042 converts/maps restartably without
sending. Destructive 0043 remains unsupplied. Historical migrations, including
0035_messaging_tenant_tie and frozen conversion helpers, are retained.

`notifications/member_push.py`, `envelope_push_leases.py`, `envelope_push_transport.py` and
`models_push.py` own registered device fan-out beneath `NotificationDelivery(native_push)`.
Notifications 0008 expands nullable parents, 0009 converts/maps old rows, 0010 verifies/enforces
parent/device uniqueness. `inbox.py::write_envelope_inbox` supplies source audience/scope and a
stable identity without triggering push; `privacy.py` owns push/inbox mapping redaction hooks.
Deleting inbox rows preserves children through their canonical parent. The entire notifications
app still owns adapter registration; disabling its inbox module is a distinct operation.

`messaging/dispatch.py` and `worker.py` and old member-push enqueue/deliver task names are inert
import/broker shims. `tasks_messaging.py` recovers canonical ingress; settings wipe tasks retain
retired-secret hygiene. Duplicate settings/template writes return 503 then 410. Source adapter
coverage and deliberate legacy pre-skips are indexed in notification-coverage.md.

Messaging analytics uses `operations/reports_communications.py::build_communications_health`
(version 4), `integrations/reports_messaging.py` and the operations canonical delivery-fact
helpers. `NotificationDelivery` plus exact legacy mappings preserve original observations
without counting another send; EmailLog and device children supply physical outcomes once.
`report_fields_hi.py` owns public fields; `org_reports_messaging.py` combines weighted rates
and excludes current consent snapshots from totals. Platform services/module health are v3;
mobile devices/auth v2. Held ingress, original abandoned receipts, current proof-bound consent
and billed-zero segments keep distinct measurements. See [measurement notes](report-builders-messaging.md).

## Public pages and shared handles

`makerspaces/public_page_*` owns the typed makerspace/organization page contract, authority,
revision projections, handles, private uploads and cleanup. `public_page_urls.py`,
`public_page_editor_urls.py` and `public_page_share_urls.py` are attached by `config/urls.py`.
`events/urls_public_codes.py` supplies venue-targeted short-event reads only while Events is active.
Release 2 L1's public event surface: `events/short_links.py` + `models_short_links.py` (codes, PII-free
visit days, `visits(event, since)` for analytics) and `views_short_links_admin.py`; `website_visibility.py`
(`public_q` access gate vs `listed_q` listing gate); `online_delivery.py` (delivery mode, the encrypted
join link and `join_url_for`, the venue `map_url`); `embed_policy.py` + `models_embed_policy.py` +
`views_embed.py` + `templates/events/embed.html` (the framable card); `share_cards.py` +
`views_event_share.py` (the 1200x630 share PNG); `report_switches.py` (DY-61);
`views_event_surface_settings.py` (embed policy, report switches, host options);
`directories.host_makerspaces` (DY-63); `makerspaces/closed_notice.py` (#77 banner). Frontend:
`features/staff/eventPublishing/` (three questions, editor fields, settings cards),
`features/events/shortLinks/`, `features/events/publicSurface.ts`, `features/public/ClosedNoticeBanner.tsx`.
`organizations/urls_public_page_collections.py` adds linked-space collections; the existing event
catalogue supplies independent upcoming and minimal past periods.

`accounts/claim_routes_public_pages.py`, `accounts/delegated_routes.py`,
`apiclients/scope_registry_public_pages.py` and `makerspaces/origin_scope_routes_public_pages.py`
classify safe reads, full-session editors, tagged tenant/global handles, venue tokens and platform
organization origins. `tenant_migration/gate_policy_public_pages.py` declares write participation.
`audit/presentation_catalog_profiles.py` labels page mutations; `presentation_discovery.py` holds
the closed `finish` wrapper vocabulary exact while keeping its dynamic metadata redacted.

`backup/public_page_registry.py` guards the four portable pointer exceptions, global ownership,
creator User edges and private object declarations. `backup/public_page_verification.py`,
`event_page_verification.py` and `event_page_draft_verification.py` check candidate database state
before deployment/slice restore checkpoints and readable-main verification. They do not fetch
public content or mutate restored documents. `makerspaces/public_page_lifecycle.py` enlists tenant
and event asset deletion before purge; the durable cleanup worker retains retry and quota ownership.
`tenant_migration/page_pointer_fixups.py` retains the separate draft-only portable import protocol.

Edge crawler dispatch lives in `frontend/nginx.conf`, `deploy/Caddyfile.saas` and
`deploy/Caddyfile.saas-install`; root-segment inventory lives in `public_profile_route_inventory.py`.
Integration regression files are `backend/tests/public_pages/test_l3_*.py`.

Cloud shared integration: config/cloud_settings composes lane contracts; operations/models_cloud_*, models_storage_capabilities and cloud_quotas own deployment-local state/projections; operations/cloud_runtime owns generation admission; scripts/cloud_entrypoint composes protected managed files before M admission. Provider/operator guides live under docs/deploy/cloud-*.md.

`backup/managed/staging.py` owns ciphertext locators/deletion receipts; `writers.py`, `presigns.py`,
`capture.py` and `recovery.py` own managed drain/reconciliation. `tenant_migration/cloud_import_*`
adapts existing import protocols to object storage. `cloud_capture_staging.py` encrypts capture trees;
`cloud_portable.py` qualifies and leases isolated scratch databases. Pure derivation manifest assembly
lives in `tenant_dump_derivation_manifest.py`; readable-main operational omissions in
`backup/main_projection_omissions.py`. `operations/cloud_jobs` remains the single periodic/work catalog
and owns bounded cursor adapters and actual scheduler diagnostics; `cloud_quotas` owns physical usage,
write reservations and audited storage/mail reconciliation. `backup/privileged_target.py`
derives only the active database-name component for privileged host jobs and validates the protected tuple.
