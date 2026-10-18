# Lane U reconciliation handoff

Branch `lane/recon-U`; wave-1 base `0579b1b3504586222655e15805370d376fbfb278`.
Changes are uncommitted and confined to U's frontend files/tests. No Docker, pytest,
Vitest, build, review gate, Codex CLI, staging, commit or Git mutation ran.

## Result

- Canonical integrations panels own channel setup, WhatsApp templates/provider approval,
  personal proofs/preferences/history and diagnostic sends. Duplicate addressed editors,
  their API client and dead copy helper are removed. Legacy room/email administration stays.
- SMS settings use canonical Twilio credentials, default off, explicit platform permission,
  own-credential precedence/removal and explicit imported-sender review. WhatsApp retains
  Twilio/Meta and now displays its independent default-off module correctly.
- SMS consent uses the retained core `/me/messaging` read and `/me/messaging/consent`
  write, separate from retired settings APIs. The service binds consent to the current
  phone instance/sender. Phone verification refreshes reads without subscribing anyone.
  WhatsApp uses canonical signed challenge/endpoint proof, never an SMS consent toggle.
- Account-only owners reach Channels through canonical permission results, independently
  of membership/inbox. Refused refreshes hide cached controls; revoked local memberships
  cannot enter. Old `section=messaging` links remain aliases. Invalidated connections can
  still be disconnected; both connection and SMS consent gates constrain category choices.
- Legacy inbox OAuth redirects preserve signed code/state and land on account Channels
  without requiring membership/inbox. Account restore and archived payments remain
  reachable while single-tenant bootstrap is unavailable.
- Staff get a core My channels tab independent of inbox. Platform keeps its separate tab
  set. Dashboard/report/settings links preserve context. Notification keys include account,
  context and tenant; switching contexts clears private caches. Mutations refresh canonical
  data; old-account completions cannot populate the next account's preferences.
- Member lifecycle operations explicitly select the member session context. There are no
  native device-login callers in this frontend: no obsolete implicit native staff caller
  remains to port. A's native context/slug/grant contract remains server-owned.
- Existing O charts, payment-provider settings and member lifecycle UI, plus T staff/
  platform separation, handover queue home, documents, presence and governance are retained.

## Migrations and model fields

None. U owns no backend app/migration. No database or cutover state was changed/activated.
The UI consumes M's SMS channel, sender/platform/hold fields, template feature/needs_review
metadata and HELD delivery state. Neither generated file nor the catalog digest was edited.

## Exact interface requests and remaining dependencies

- **M: staff SMS diagnostics.** `notification_api_delivery.ContractTestView` queues a test
  to the Space Manager's own staff account; `notification_addressed.eligible` requires
  `live_consent`. But `messaging.consent.member_space` uses member-only `has_tenant_tie`,
  so staff cannot grant that consent. Supply an account-kind-safe canonical staff SMS
  consent/read contract (active local staff, own verified phone, sender/generation binding),
  or explicitly define unsupported staff SMS diagnostics. U shows the sanitized refusal
  and does not bypass consent. No unowned backend file changed.
- **G: schema.** Regenerate OpenAPI/TypeScript after A/M/P/R/C converge. Existing consumers
  need MemberUsage/MemberUsageSeries, ReportChartSpec, DashboardWidget, Dashboard widgets/
  queue_tiles/handover scope, ReportCatalogItem chart_spec/identity_bearing,
  OrganizationReportResponse chart_spec, AnalyticsMakerspace/Page, PlatformAnalyticsReport,
  M's canonical fields above, and A's native context/slug/device-grant response additions.
- **Claude/G: validation.** Collect/run transported tests using frozen runner configs,
  build after regeneration, and run real-stack settings/consent/OAuth/account-context/
  documents/charts flows. Static typecheck exits 1 with 47 diagnostics: missing generated
  analytics shapes and existing report fixtures missing required catalog fields. The full
  log is retained. These are not claimed as approved D4 baseline exceptions; provenance,
  reproduction and any post-merge treatment remain with the orchestrator.
- **G: transport.** Apply the ignored test delta and its deletion tombstones. Three retired
  duplicate suites have explicit canonical replacements in the JSON manifest. Stamp the
  eventual implementation commit after Claude commits. Review/QA and operational cutover
  remain outside U. No frontend file appears in the supplied suite-conflict list.

## Verification and artifact transport

All 1,453 frontend TS/TSX files parse without syntax errors. `git diff --check` passes;
touched production TS/TSX files are below 300 lines; index is empty; no protected,
generated or backend path changed. No frontend conflict marker or U note remains.
No runtime tests or collection ran, per the owner instruction.

The supplied wave-1 manifest matches all 483 overlapping frontend verification files in
the initial U snapshot. The extra unchanged local file is
`frontend/scripts/verify-website-serving.test.mjs`, absent from G's manifest; parent
provenance is not inferred for it.

Artifacts: `frontend/e2e/_reconciliation_artifacts/` in this worktree. Claude must transport
them to G's durable store. `lane_U_handoff.json` records original/result hashes, supplied
G/base hashes, source hashes, changed tests, tombstones, commands and verification limits.
`lane_U_tests_delta.zip` contains changed/new ignored tests; `lane_U_base.zip` preserves
the initial verification snapshot. The complete static log is `typecheck-final.log`;
other evidence is in `syntax-check.json` and `line-and-ownership-check.json`.

Delta SHA-256: `8cf61b97db30e13a72ec9ee01da785b46ad6380df594586c218abfc08ad67e90`.

Suggested changed-area suites: notifications; MemberMessagingTies; MemberPortalTabs;
MemberAccount/MemberArea/deletion; staff navigation/access; dashboard/module/platform
analytics; AppRoutes.reconciliation; App.recovery; SessionBoundary.reconciliation.
Use G's restored runner configurations. No baseline-failure exemption is asserted.

## Files changed

The exact source and test lists follow; hashes and deleted-test replacement mapping are
in the JSON handoff. Source deletions retire duplicate runtime UI, not historical backend
models, migrations, compatibility ingress or retained consent APIs.

- `frontend/src/App.tsx`
- `frontend/src/AppRoutes.tsx`
- `frontend/src/features/members/MemberAccountPage.tsx`
- `frontend/src/features/members/MemberArea.tsx`
- `frontend/src/features/members/MemberMessaging.tsx` (deleted)
- `frontend/src/features/members/MemberPhoneVerification.tsx`
- `frontend/src/features/members/MemberScreenLayout.tsx`
- `frontend/src/features/members/accountDeletionApi.ts`
- `frontend/src/features/messaging/MessagingFeedback.tsx`
- `frontend/src/features/messaging/messagingApi.ts` (deleted)
- `frontend/src/features/notifications/ChannelDeliveryLog.tsx`
- `frontend/src/features/notifications/ChannelPreferences.tsx`
- `frontend/src/features/notifications/ChannelSetupForm.tsx`
- `frontend/src/features/notifications/ChannelSetupPanel.tsx`
- `frontend/src/features/notifications/ChannelTestSend.tsx`
- `frontend/src/features/notifications/MyNotificationSettings.tsx`
- `frontend/src/features/notifications/PersonalChannels.tsx`
- `frontend/src/features/notifications/SmsConsent.tsx`
- `frontend/src/features/notifications/WhatsAppTemplatesEditor.tsx`
- `frontend/src/features/notifications/channelCatalog.ts`
- `frontend/src/features/notifications/channelsApi.ts`
- `frontend/src/features/notifications/smsConsentApi.ts`
- `frontend/src/features/staff/MakerspaceMessagingSettings.tsx` (deleted)
- `frontend/src/features/staff/MakerspaceSettingsPanel.tsx`
- `frontend/src/features/staff/MessagingTestSend.tsx` (deleted)
- `frontend/src/features/staff/NotificationChannelPreferences.tsx`
- `frontend/src/features/staff/PlatformDashboardPanel.tsx`
- `frontend/src/features/staff/SettingsHub.tsx`
- `frontend/src/features/staff/StaffTabContent.tsx`
- `frontend/src/features/staff/WhatsAppBindingForm.tsx` (deleted)
- `frontend/src/features/staff/WhatsAppTemplateBindings.tsx` (deleted)
- `frontend/src/features/staff/panels/DashboardAnalyticsWidgets.tsx`
- `frontend/src/features/staff/panels/DashboardPanel.tsx`
- `frontend/src/features/staff/panels/ModuleAnalytics.tsx`
- `frontend/src/features/staff/panels/NotificationInbox.tsx`
- `frontend/src/features/staff/panels/dashboardLinks.ts`
- `frontend/src/features/staff/settingsHubCatalog.ts`
- `frontend/src/features/staff/sidebarSections.ts`
- `frontend/src/features/staff/staffAccess.ts`
- `frontend/src/lib/SessionBoundary.tsx`
- `frontend/src/test/messagingFixtures.tsx`

## Ignored tests added/updated

- `frontend/src/App.recovery.test.tsx`
- `frontend/src/AppRoutes.reconciliation.test.tsx`
- `frontend/src/features/members/MemberMessagingTies.test.tsx`
- `frontend/src/features/notifications/ChannelSetup.test.tsx`
- `frontend/src/features/notifications/PersonalChannels.test.tsx`
- `frontend/src/features/notifications/SmsConsent.test.tsx`
- `frontend/src/features/staff/NotificationMessagingChannels.test.tsx`
- `frontend/src/features/staff/panels/DashboardPanel.test.tsx`
- `frontend/src/features/staff/panels/ModuleAnalytics.test.tsx`
- `frontend/src/features/staff/panels/dashboardLinks.test.ts`
- `frontend/src/features/staff/rbacF6.test.ts`
- `frontend/src/features/staff/staffTabs.test.ts`
- `frontend/src/lib/SessionBoundary.reconciliation.test.tsx`

Deleted duplicate tests (canonical replacements recorded in JSON):

- `frontend/src/features/members/MemberMessaging.test.tsx`
- `frontend/src/features/staff/MakerspaceMessagingSettings.test.tsx`
- `frontend/src/features/staff/WhatsAppTemplateBindings.test.tsx`
