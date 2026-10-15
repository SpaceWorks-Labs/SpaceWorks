# Wave-3 file-ownership manifest (`OWNERSHIP.md`)

Required by `PLAN.md` §4 "Wave 3 — every screen". Every `.ts`/`.tsx` file under `frontend/src/features/**`, plus `frontend/src/App.tsx`, `frontend/src/AppRoutes.tsx`, their root-level tests, and `frontend/e2e/*.ts`, appears in **exactly one** section below. A lane may edit only the files in its own table; Codex prompts for a lane include that table verbatim. Generated 2026-10-15 on `feature/design-revamp` @ `55e36d64` (pre-wave-2: `components/layouts`, `components/shell` and `sidebarSections.ts` do not exist yet).

## How it was built

1. **Seeds** — each lane's screen roots from PLAN §4 + `ux-yuyu-spec.md` §3 (S1–S24) + `ux-screens-longtail.md` (A–J, §14 coverage table; tab → component via `StaffTabLoaders.tsx`).
2. **Closure** — BFS over every relative import (`from "./…"`, `from "../…"`, `import("…")`, re-exports) inside the universe. The walk stops at FROZEN files, coordinator files and another lane's seed (that seed is *consumed unchanged*).
3. **Overlaps** — PLAN's resolved overlaps applied first (A8 delivery logs/suppressions → admin; C6 member account → public; `PaymentDocuments.tsx` + payment dialogs → desk). Every other file reached by two lanes went to its primary consumer (most importers / the spec that names it / its directory family); the other lane is listed under *Consumes unchanged*. Files shared by **three or more lanes** (barrels, list chrome, cache helpers) are coordinator-owned instead of being handed to one lane.
4. **Tests** — gitignored `*.test.ts(x)` follow the component of the same basename (`X.test.tsx`, `X.foo.test.tsx` → `X.tsx`); otherwise the owner of the files they import. e2e specs touching two lanes → coordinator.
5. Scripts: `graph.py` (import graph), `assign.py` (seeds + BFS + overlap report), `build.py` (this file), `check.py` (uniqueness + completeness) in the session scratchpad.

### Judgement calls (overlaps not settled by PLAN)

- **Payments** — `PaymentsPanel`, the three dialogs, `PaymentReconcileActions`, `PaymentDueBadge`, `paymentsApi.ts`, `paymentAccess.ts` and `payments/PaymentDocuments.tsx` → desk (PLAN resolved overlap). Public (`MemberPayments`), admin (`MembersPanel`, membership plans) and ops (`BookingDrawer`, `EventRegistrationRoster`, `OperationsReports`) consume them unchanged.
- **Issue/return evidence** — `panels/EvidenceUpload.tsx`, `evidenceUi.ts`, `inventory/KitChecklist.tsx`, `panels/LoanTimeline.tsx` → desk (S3/S4 handover flows are the primary consumers). Kiosk/self-checkout (public) and InventoryWorkspace (inventory) consume unchanged. Evidence/QR/remark hard rules stay untouched either way.
- **Kiosk replay** — staff-side `KioskReplayRecoveryPanel` + `KioskReplayResolution` (rendered by `RequestsPanel`) → desk; the rest of `kiosk/` incl. `KioskReplayDetail`, `useKioskReplays`, `kioskReplayApi` → public (S23 kiosk family).
- **Event check-in offline** — `OfflineCheckInOperator.tsx`, `eventCheckInOfflineApi.ts`, `eventCheckInOfflineStore.ts` → ops (named by S12 Check-in tab; live in `staff/`). `EventCheckInStationPage` (I1, public) consumes unchanged.
- **Custom forms** — staff-side `CustomFormBuilder` + `CustomAnswersView` → ops; respondent-side `CustomFormFields` + `customFormTypes.ts` → public.
- **Notifications** — `PersonalInbox.tsx` → ops (A7 names it); member inbox (H5) consumes unchanged; A8 `DeliveryLogScreen`/`SuppressionAdmin` → admin (PLAN). Notification destinations / recipient picker family → admin (S9 settings); `MachinesPanel` consumes unchanged.
- **Machines API** (`machinesApi.ts`, `machinesApi/*`, consumables/documents API) → ops; `ProcurementMoveModal` (inventory) consumes unchanged. `panels/DashboardMachineQueue.tsx` is imported only by `MachinesPanel` despite its name → ops.
- **Member cards** — `panels/memberCards/*` incl. `ScanCardBox` → ops (A12); the S3 issue flow (desk) consumes `ScanCardBox` unchanged.
- **Warranty** — `WarrantySection`, `WarrantyStatusBadge`, `warrantyApi.ts` → inventory (A10); machine `WarrantyTab` (ops) consumes unchanged.
- **MFA** — `auth/MfaFlow.tsx` + `mfaApi.ts` → public (F2); `auth/MfaAccountPage.tsx` → admin (PLAN lists C7 under admin).
- **Shell-adjacent** — `StaffDock`, `StaffDockPopover`, `useDockAnchor`, `staffNavIcons`, `useUnreadNotifications`, `StaffHeader`, `SetupChecklist(+State)`, `StaffTabLoaders` added to FROZEN: wave-2 `dr-shell` replaces or rewires them.
- **Batch F gates** (`ChangePasswordGate`, `StaffAccessDenied`, `RecoveryQuarantinePanel`, `StaffPanelErrorBoundary`, `MfaFlow`, `AppRoutes` NotFound/FamilyHome/RouteFallback, `App.tsx` tenant gates) → public, per PLAN (`Batch F` under `dr-screens-public`).
- **Lane sizes are uneven** (source files: ops 142, public 147, admin 119, desk 45, inventory 36). That reflects PLAN's split; it is not an error in the manifest.

## 0. Summary

| section | source | tests (unit + e2e) | total |
|---|---|---|---|
| dr-screens-desk | 45 | 22 | 67 |
| dr-screens-inventory | 36 | 5 | 41 |
| dr-screens-admin | 119 | 41 | 160 |
| dr-screens-ops | 142 | 40 | 182 |
| dr-screens-public | 147 | 77 | 224 |
| FROZEN | 18 | 13 | 31 |
| COORD | 7 | 8 | 15 |
| UNTOUCHED | 8 | 1 | 9 |
| **all** | 522 | 207 | 729 |

## 1. Lanes

## `dr-screens-desk`

### `dr-screens-desk` — source (45 files)

| path | lines | screen / spec |
|---|---|---|
| `frontend/src/features/inventory/KitChecklist.tsx` | 83 | via DirectLoans.tsx (S4) |
| `frontend/src/features/kiosk/KioskReplayRecoveryPanel.tsx` | 44 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/kiosk/KioskReplayResolution.tsx` | 50 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/payments/PaymentDocuments.tsx` | 56 | A1/H4 (resolved overlap) |
| `frontend/src/features/staff/DirectLoanIssueFields.tsx` | 259 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/DirectLoanList.tsx` | 123 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/DirectLoanReturnModal.tsx` | 253 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/DirectLoans.tsx` | 282 | S4 |
| `frontend/src/features/staff/DirectLoansTypes.ts` | 36 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/MemberClaimCodes.tsx` | 144 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/PaymentDueBadge.tsx` | 13 | A1 |
| `frontend/src/features/staff/PaymentReconcileActions.tsx` | 95 | A1 (§14.3) |
| `frontend/src/features/staff/PaymentRefundDialog.tsx` | 180 | A1/J4 |
| `frontend/src/features/staff/PaymentsPanel.tsx` | 233 | A1 |
| `frontend/src/features/staff/RefundReceiptAmendDialog.tsx` | 37 | A1/J4 |
| `frontend/src/features/staff/SettlementDialog.tsx` | 108 | A1/J4 |
| `frontend/src/features/staff/StaffLoanRenew.tsx` | 23 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/WalkInMemberForm.tsx` | 159 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/evidenceUi.ts` | 13 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/handover/DirectHandoverWizard.tsx` | 87 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/handover/HandoverBoxScan.tsx` | 29 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/handover/HandoverItems.tsx` | 37 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/handover/HandoverWizard.tsx` | 87 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/issueErrors.ts` | 15 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/DashboardPanel.tsx` | 105 | S1 |
| `frontend/src/features/staff/panels/EvidenceUpload.tsx` | 132 | via DirectLoans.tsx (S4) |
| `frontend/src/features/staff/panels/LoanTimeline.tsx` | 150 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/Queues.tsx` | 2 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesAcceptModal.tsx` | 90 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesAssignIssueModal.tsx` | 125 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesDisplay.tsx` | 57 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesInvalidation.ts` | 33 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesList.tsx` | 141 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesModalShared.tsx` | 104 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesModalTypes.ts` | 50 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesModals.tsx` | 82 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesReturnRequestModal.tsx` | 175 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/QueuesSkeleton.tsx` | 18 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/RequestQueues.tsx` | 238 | via RequestsPanel.tsx (S2/S3) |
| `frontend/src/features/staff/panels/RequestsPanel.tsx` | 7 | S2/S3 |
| `frontend/src/features/staff/panels/dashboardLinks.ts` | 29 | via DashboardPanel.tsx (S1) |
| `frontend/src/features/staff/panels/machine/HandoverConsole.tsx` | 104 | A17 (S24 Job pickups) |
| `frontend/src/features/staff/paymentAccess.ts` | 19 | via PaymentsPanel.tsx (A1) |
| `frontend/src/features/staff/paymentsApi.ts` | 208 | via PaymentsPanel.tsx (A1) |
| `frontend/src/features/staff/useDirectLoanReturn.ts` | 83 | via DirectLoans.tsx (S4) |

### `dr-screens-desk` — gitignored tests (22 files)

| path | lines | follows |
|---|---|---|
| `frontend/src/features/inventory/KitChecklist.test.tsx` | 52 | tests KitChecklist.tsx |
| `frontend/src/features/kiosk/KioskReplayRecoveryPanel.test.tsx` | 103 | tests KioskReplayRecoveryPanel.tsx |
| `frontend/src/features/payments/PaymentDocuments.test.tsx` | 52 | tests PaymentDocuments.tsx |
| `frontend/src/features/staff/MemberClaimCodes.test.tsx` | 90 | tests MemberClaimCodes.tsx |
| `frontend/src/features/staff/PaymentOfflineRefund.test.tsx` | 72 | imports PaymentRefundDialog.tsx, PaymentsPanel.tsx, paymentsApi.ts |
| `frontend/src/features/staff/PaymentReconcileActions.test.tsx` | 57 | tests PaymentReconcileActions.tsx |
| `frontend/src/features/staff/PaymentRefundDialog.test.tsx` | 105 | tests PaymentRefundDialog.tsx |
| `frontend/src/features/staff/PaymentsF6.test.tsx` | 44 | imports PaymentsPanel.tsx |
| `frontend/src/features/staff/PaymentsPanel.test.tsx` | 184 | tests PaymentsPanel.tsx |
| `frontend/src/features/staff/StaffLoanRenew.test.tsx` | 22 | tests StaffLoanRenew.tsx |
| `frontend/src/features/staff/WalkInMemberForm.test.tsx` | 67 | tests WalkInMemberForm.tsx |
| `frontend/src/features/staff/evidenceUi.test.ts` | 22 | tests evidenceUi.ts |
| `frontend/src/features/staff/handover/DirectHandoverWizard.test.tsx` | 63 | tests DirectHandoverWizard.tsx |
| `frontend/src/features/staff/handover/HandoverWizard.test.tsx` | 78 | tests HandoverWizard.tsx |
| `frontend/src/features/staff/panels/DashboardPanel.familyOnly.test.tsx` | 40 | tests DashboardPanel.tsx |
| `frontend/src/features/staff/panels/DashboardPanel.test.tsx` | 84 | tests DashboardPanel.tsx |
| `frontend/src/features/staff/panels/LoanTimeline.test.tsx` | 95 | tests LoanTimeline.tsx |
| `frontend/src/features/staff/panels/QueuesDrilldown.test.tsx` | 19 | imports Queues.tsx |
| `frontend/src/features/staff/panels/dashboardLinks.test.ts` | 18 | tests dashboardLinks.ts |
| `frontend/src/features/staff/rbacF6.test.ts` | 51 | imports paymentAccess.ts, paymentsApi.ts, staffAccess.ts |
| `frontend/e2e/hard-rules.spec.ts` | 54 | issue/return evidence hard rules S3 |
| `frontend/e2e/request-lifecycle.spec.ts` | 51 | accept/issue/return S2/S3 |

## `dr-screens-inventory`

### `dr-screens-inventory` — source (36 files)

| path | lines | screen / spec |
|---|---|---|
| `frontend/src/features/staff/WarrantySection.tsx` | 256 | via ContainersPanel.tsx (A16/B3) |
| `frontend/src/features/staff/WarrantyStatusBadge.tsx` | 20 | via WarrantyPanel.tsx (A10) |
| `frontend/src/features/staff/panels/AssetEditForm.tsx` | 105 | via Inventory.tsx (S5/S6) |
| `frontend/src/features/staff/panels/BulkImport.tsx` | 204 | E1 |
| `frontend/src/features/staff/panels/BulkImportHelpers.ts` | 137 | via BulkImport.tsx (E1) |
| `frontend/src/features/staff/panels/Categories.tsx` | 226 | A15 |
| `frontend/src/features/staff/panels/ContainersPanel.tsx` | 146 | A16/B3 |
| `frontend/src/features/staff/panels/Inventory.tsx` | 1 | S5/S6 |
| `frontend/src/features/staff/panels/InventoryPanelParts.tsx` | 209 | via Inventory.tsx (S5/S6) |
| `frontend/src/features/staff/panels/InventoryPanelShared.ts` | 75 | via Inventory.tsx (S5/S6) |
| `frontend/src/features/staff/panels/InventoryWorkspace.tsx` | 283 | via Inventory.tsx (S5/S6) |
| `frontend/src/features/staff/panels/Ledger.tsx` | 195 | A2 |
| `frontend/src/features/staff/panels/LedgerParts.tsx` | 138 | via Ledger.tsx (A2) |
| `frontend/src/features/staff/panels/NeedsFixShelf.tsx` | 94 | A6 |
| `frontend/src/features/staff/panels/ProcurementMoveForms.tsx` | 109 | via ProcurementPanel.tsx (A5) |
| `frontend/src/features/staff/panels/ProcurementMoveModal.tsx` | 167 | via ProcurementPanel.tsx (A5) |
| `frontend/src/features/staff/panels/ProcurementPanel.tsx` | 240 | A5 |
| `frontend/src/features/staff/panels/ProcurementPanelRows.tsx` | 153 | via ProcurementPanel.tsx (A5) |
| `frontend/src/features/staff/panels/ProcurementPanelTypes.ts` | 28 | via ProcurementPanel.tsx (A5) |
| `frontend/src/features/staff/panels/ProcurementReceipts.tsx` | 123 | via ProcurementPanel.tsx (A5) |
| `frontend/src/features/staff/panels/ProductMasterFields.tsx` | 24 | via Inventory.tsx (S5/S6) |
| `frontend/src/features/staff/panels/QrImage.tsx` | 26 | via ContainersPanel.tsx (A16/B3) |
| `frontend/src/features/staff/panels/QrTools.tsx` | 266 | E2 |
| `frontend/src/features/staff/panels/ReorderSuggestions.tsx` | 33 | via Inventory.tsx (S5/S6) |
| `frontend/src/features/staff/panels/ScannerPanel.tsx` | 291 | Staff Scanner tab (§10) |
| `frontend/src/features/staff/panels/ScannerPanelForms.tsx` | 164 | via ScannerPanel.tsx (Staff Scanner tab (§10)) |
| `frontend/src/features/staff/panels/ScannerPanelTypes.ts` | 17 | via ScannerPanel.tsx (Staff Scanner tab (§10)) |
| `frontend/src/features/staff/panels/StockTransferPanel.tsx` | 279 | A3 |
| `frontend/src/features/staff/panels/StockTransferTable.tsx` | 60 | via StockTransferPanel.tsx (A3) |
| `frontend/src/features/staff/panels/StocktakeCountSection.tsx` | 202 | via StocktakeSessionPanel.tsx (B2) |
| `frontend/src/features/staff/panels/StocktakeDiscipline.tsx` | 40 | via StocktakeSessionPanel.tsx (B2) |
| `frontend/src/features/staff/panels/StocktakePanel.tsx` | 1 | A4 |
| `frontend/src/features/staff/panels/StocktakeSessionPanel.tsx` | 109 | B2 |
| `frontend/src/features/staff/panels/WarrantyPanel.tsx` | 202 | A10 |
| `frontend/src/features/staff/panels/useInventoryArchive.ts` | 47 | via Inventory.tsx (S5/S6) |
| `frontend/src/features/staff/warrantyApi.ts` | 124 | via WarrantyPanel.tsx (A10) |

### `dr-screens-inventory` — gitignored tests (5 files)

| path | lines | follows |
|---|---|---|
| `frontend/src/features/staff/panels/InventoryDrilldown.test.tsx` | 22 | imports Inventory.tsx, shared.tsx |
| `frontend/src/features/staff/panels/ProcurementPanel.test.ts` | 83 | tests ProcurementPanel.tsx |
| `frontend/src/features/staff/panels/ReorderSuggestions.test.tsx` | 23 | tests ReorderSuggestions.tsx |
| `frontend/src/features/staff/panels/StocktakeCountSection.test.tsx` | 36 | tests StocktakeCountSection.tsx |
| `frontend/src/features/staff/panels/useInventoryArchive.test.tsx` | 64 | tests useInventoryArchive.ts |

## `dr-screens-admin`

### `dr-screens-admin` — source (119 files)

| path | lines | screen / spec |
|---|---|---|
| `frontend/src/features/auth/MfaAccountPage.tsx` | 41 | C7 |
| `frontend/src/features/notifications/DeliveryLogScreen.tsx` | 79 | A8 |
| `frontend/src/features/notifications/SuppressionAdmin.tsx` | 42 | A8 |
| `frontend/src/features/staff/AbandonedUploadCleanupSection.tsx` | 85 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/ApiClientCreateCard.tsx` | 156 | via ApiClientsPanel.tsx (C1) |
| `frontend/src/features/staff/ApiClientListCard.tsx` | 166 | via ApiClientsPanel.tsx (C1) |
| `frontend/src/features/staff/ApiClientScopePicker.tsx` | 61 | via ApiClientsPanel.tsx (C1) |
| `frontend/src/features/staff/ApiClientsAccessSummary.tsx` | 40 | via ApiClientsPanel.tsx (C1) |
| `frontend/src/features/staff/ApiClientsPanel.tsx` | 182 | C1 |
| `frontend/src/features/staff/ApiClientsTelegramSettings.tsx` | 145 | via ApiClientsPanel.tsx (C1) |
| `frontend/src/features/staff/BackupRestorePanel.tsx` | 99 | C4 |
| `frontend/src/features/staff/BillingDocumentsSettings.tsx` | 44 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/DataExportsPanel.tsx` | 139 | A14 |
| `frontend/src/features/staff/EvidenceRetentionPanel.tsx` | 112 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/IntegrationHealthPanel.tsx` | 251 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/IntegrationHealthRooms.tsx` | 117 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/InvitationRequestsSection.tsx` | 98 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/KioskStationSettings.tsx` | 94 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceArchiveRequestPanel.tsx` | 211 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceBookingRulesSettings.tsx` | 227 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceBookingSettings.tsx` | 50 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceBrandingSettings.tsx` | 163 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceCustomDomainSettings.tsx` | 247 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceEmailSettings.tsx` | 276 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceFeatureSettings.tsx` | 87 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceFilamentSettings.tsx` | 93 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceGeneralSettings.tsx` | 120 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceGeofenceSettings.tsx` | 45 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceHoursEditor.tsx` | 50 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceLoanPolicySettings.tsx` | 74 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceLoanSettings.tsx` | 198 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceLocationSettings.tsx` | 118 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceMembershipSettings.tsx` | 109 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspacePaymentSettings.tsx` | 185 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspacePicker.tsx` | 75 | D4 |
| `frontend/src/features/staff/MakerspaceProfileSettings.tsx` | 85 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspacePublicSiteSettings.tsx` | 30 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspacePublicStatsSettings.tsx` | 98 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceReminderSettings.tsx` | 72 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceSettingsPanel.tsx` | 271 | S9 |
| `frontend/src/features/staff/MakerspaceSubdomainSettings.tsx` | 140 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceThemeSettings.tsx` | 87 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MakerspaceWebhookSettings.tsx` | 164 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MemberTermsDialog.tsx` | 114 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/MembersPanel.tsx` | 179 | S7 |
| `frontend/src/features/staff/MembershipAdmissionReview.tsx` | 34 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/MembershipAdmissionSettings.tsx` | 77 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/MembershipPagination.tsx` | 10 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/MembershipPlanPicker.tsx` | 18 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/MembershipPlansSection.tsx` | 180 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/MembershipReasonDialog.tsx` | 18 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/MembershipRenewalFields.tsx` | 29 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/MembershipWaiverPanel.tsx` | 34 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/ModulesPanel.tsx` | 220 | C2 |
| `frontend/src/features/staff/NotificationChannelPreferences.tsx` | 201 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/NotificationDestinations.tsx` | 110 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/NotificationMuteMatrix.tsx` | 237 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/NotificationRecipientEvent.tsx` | 219 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/NotificationRecipientPicker.tsx` | 121 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/NotificationTimingSettings.tsx` | 32 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/OrganizationInvitations.tsx` | 64 | via OrganizationsPanel.tsx (C5) |
| `frontend/src/features/staff/OrganizationMemberships.tsx` | 44 | via OrganizationsPanel.tsx (C5) |
| `frontend/src/features/staff/OrganizationProfileForm.tsx` | 60 | via OrganizationsPanel.tsx (C5) |
| `frontend/src/features/staff/OrganizationSetup.tsx` | 38 | via OrganizationsPanel.tsx (C5) |
| `frontend/src/features/staff/PlatformDashboardPanel.tsx` | 53 | D1 |
| `frontend/src/features/staff/PlatformEmailPanel.tsx` | 135 | C3 |
| `frontend/src/features/staff/PlatformSocialAuthPanel.tsx` | 105 | C3 |
| `frontend/src/features/staff/PlatformStripeConnectPanel.tsx` | 138 | C3 |
| `frontend/src/features/staff/SpacePackProfilePicker.tsx` | 27 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/SpacePacksPanel.tsx` | 78 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/TenantMigrationDisclosure.tsx` | 131 | via TenantMigrationPanel.tsx (E4) |
| `frontend/src/features/staff/TenantMigrationExports.tsx` | 172 | via TenantMigrationPanel.tsx (E4) |
| `frontend/src/features/staff/TenantMigrationIdentityDecisions.tsx` | 125 | via TenantMigrationPanel.tsx (E4) |
| `frontend/src/features/staff/TenantMigrationImports.tsx` | 198 | via TenantMigrationPanel.tsx (E4) |
| `frontend/src/features/staff/TenantMigrationPairings.tsx` | 104 | via TenantMigrationPanel.tsx (E4) |
| `frontend/src/features/staff/TenantMigrationPanel.tsx` | 53 | E4 |
| `frontend/src/features/staff/TenantUsagePanel.tsx` | 38 | D2 |
| `frontend/src/features/staff/apiClientsApi.ts` | 127 | via ApiClientsPanel.tsx (C1) |
| `frontend/src/features/staff/backupApi.ts` | 59 | via BackupRestorePanel.tsx (C4) |
| `frontend/src/features/staff/dataExportsApi.ts` | 38 | via DataExportsPanel.tsx (A14) |
| `frontend/src/features/staff/evidenceRetentionApi.ts` | 91 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/makerspaceProfileForm.ts` | 55 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/membershipPlansApi.ts` | 123 | via MembersPanel.tsx (S7) |
| `frontend/src/features/staff/notificationDestinationTypes.ts` | 52 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/notificationDestinations/DestinationForm.tsx` | 185 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/notificationDestinations/DestinationRow.tsx` | 64 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/notificationDestinations/ScopePicker.tsx` | 58 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/notificationDestinations/channels.ts` | 11 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/notificationDestinations/scopeOptions.ts` | 56 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/notificationRuleTypes.ts` | 49 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/organizationAnalyticsApi.ts` | 43 | via OrganizationAnalyticsPanel.tsx (D3) |
| `frontend/src/features/staff/organizationsApi.ts` | 141 | via OrganizationsPanel.tsx (C5) |
| `frontend/src/features/staff/panels/DeliveryLogPanel.tsx` | 6 | A8 |
| `frontend/src/features/staff/panels/EmailLogPanel.tsx` | 171 | A8 |
| `frontend/src/features/staff/panels/EmailTemplateEditor.tsx` | 297 | via EmailTemplatesPanel.tsx (A18/B1) |
| `frontend/src/features/staff/panels/EmailTemplateTypeSelector.tsx` | 63 | via EmailTemplatesPanel.tsx (A18/B1) |
| `frontend/src/features/staff/panels/EmailTemplatesPanel.tsx` | 186 | A18/B1 |
| `frontend/src/features/staff/panels/OrganizationAnalyticsPanel.tsx` | 184 | D3 |
| `frontend/src/features/staff/panels/OrganizationsPanel.tsx` | 47 | C5 |
| `frontend/src/features/staff/panels/RoleEditor.tsx` | 93 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/RoleMachineScopeEditor.tsx` | 143 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/RoleManager.tsx` | 74 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/StaffInvitations.tsx` | 48 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/Users.tsx` | 279 | S8/E3 |
| `frontend/src/features/staff/panels/UsersModals.tsx` | 15 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/UsersTable.tsx` | 84 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/rolesApi.ts` | 99 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/users/forms.ts` | 52 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/usersModals/AddStaffModal.tsx` | 66 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/usersModals/CreateMakerspaceModal.tsx` | 43 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/usersModals/CreationWizardSteps.tsx` | 39 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/usersModals/ResetPasswordModal.tsx` | 102 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/usersModals/RestrictUserModal.tsx` | 43 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/usersModals/shared.tsx` | 45 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/panels/usersModals/types.ts` | 24 | via Users.tsx (S8/E3) |
| `frontend/src/features/staff/platformMonitoringApi.ts` | 31 | via TenantUsagePanel.tsx (D2) |
| `frontend/src/features/staff/spacePacksApi.ts` | 25 | via MakerspaceSettingsPanel.tsx (S9) |
| `frontend/src/features/staff/tenantMigrationApi.ts` | 123 | via TenantMigrationPanel.tsx (E4) |
| `frontend/src/features/staff/tenantMigrationUi.tsx` | 78 | via TenantMigrationPanel.tsx (E4) |

### `dr-screens-admin` — gitignored tests (41 files)

| path | lines | follows |
|---|---|---|
| `frontend/src/features/staff/ApiClientScopePicker.test.tsx` | 56 | tests ApiClientScopePicker.tsx |
| `frontend/src/features/staff/ApiClientsPanel.test.tsx` | 172 | tests ApiClientsPanel.tsx |
| `frontend/src/features/staff/BackupRestorePanel.test.tsx` | 83 | tests BackupRestorePanel.tsx |
| `frontend/src/features/staff/BillingDocumentsSettings.test.tsx` | 36 | tests BillingDocumentsSettings.tsx |
| `frontend/src/features/staff/DataExportsPanel.test.tsx` | 40 | tests DataExportsPanel.tsx |
| `frontend/src/features/staff/EvidenceRetentionPanel.test.tsx` | 114 | tests EvidenceRetentionPanel.tsx |
| `frontend/src/features/staff/IntegrationHealthPanel.test.tsx` | 104 | tests IntegrationHealthPanel.tsx |
| `frontend/src/features/staff/InvitationRequestsSection.test.tsx` | 79 | tests InvitationRequestsSection.tsx |
| `frontend/src/features/staff/KioskStationSettings.test.tsx` | 31 | tests KioskStationSettings.tsx |
| `frontend/src/features/staff/MakerspaceArchiveRequestPanel.test.tsx` | 100 | tests MakerspaceArchiveRequestPanel.tsx |
| `frontend/src/features/staff/MakerspaceLoanPolicySettings.test.tsx` | 50 | tests MakerspaceLoanPolicySettings.tsx |
| `frontend/src/features/staff/MakerspaceLoanSettings.test.tsx` | 98 | tests MakerspaceLoanSettings.tsx |
| `frontend/src/features/staff/MakerspaceMembershipSettings.test.tsx` | 100 | tests MakerspaceMembershipSettings.tsx |
| `frontend/src/features/staff/MakerspacePaymentSettings.test.tsx` | 100 | tests MakerspacePaymentSettings.tsx |
| `frontend/src/features/staff/MakerspaceProfileSettings.test.tsx` | 170 | tests MakerspaceProfileSettings.tsx |
| `frontend/src/features/staff/MakerspacePublicSiteSettings.test.tsx` | 38 | tests MakerspacePublicSiteSettings.tsx |
| `frontend/src/features/staff/MakerspaceReminderSettings.test.tsx` | 57 | tests MakerspaceReminderSettings.tsx |
| `frontend/src/features/staff/MakerspaceThemeSettings.test.tsx` | 91 | tests MakerspaceThemeSettings.tsx |
| `frontend/src/features/staff/MembersF6.test.tsx` | 62 | imports MembersPanel.tsx |
| `frontend/src/features/staff/MembersPanel.test.tsx` | 214 | tests MembersPanel.tsx |
| `frontend/src/features/staff/MembershipAdmissionReview.test.tsx` | 26 | tests MembershipAdmissionReview.tsx |
| `frontend/src/features/staff/MembershipAdmissionSettings.test.tsx` | 46 | tests MembershipAdmissionSettings.tsx |
| `frontend/src/features/staff/MembershipPagination.test.tsx` | 14 | tests MembershipPagination.tsx |
| `frontend/src/features/staff/MembershipPlanPicker.test.tsx` | 22 | tests MembershipPlanPicker.tsx |
| `frontend/src/features/staff/MembershipPlansSection.test.tsx` | 125 | tests MembershipPlansSection.tsx |
| `frontend/src/features/staff/MembershipReasonDialog.test.tsx` | 20 | tests MembershipReasonDialog.tsx |
| `frontend/src/features/staff/MembershipRenewalFields.test.tsx` | 15 | tests MembershipRenewalFields.tsx |
| `frontend/src/features/staff/MembershipWaiverPanel.test.tsx` | 21 | tests MembershipWaiverPanel.tsx |
| `frontend/src/features/staff/NotificationRecipientPicker.test.tsx` | 38 | tests NotificationRecipientPicker.tsx |
| `frontend/src/features/staff/PlatformConfigurationStates.test.tsx` | 47 | imports PlatformEmailPanel.tsx, PlatformSocialAuthPanel.tsx, PlatformStripeConnectPanel.tsx, StaffPanels.tsx |
| `frontend/src/features/staff/PlatformSocialAuthPanel.test.tsx` | 73 | tests PlatformSocialAuthPanel.tsx |
| `frontend/src/features/staff/PlatformStripeConnectPanel.test.tsx` | 136 | tests PlatformStripeConnectPanel.tsx |
| `frontend/src/features/staff/SpacePacksPanel.test.tsx` | 75 | tests SpacePacksPanel.tsx |
| `frontend/src/features/staff/TenantMigrationPanel.test.tsx` | 273 | tests TenantMigrationPanel.tsx |
| `frontend/src/features/staff/devicesNotificationMatrix.test.tsx` | 22 | imports NotificationChannelPreferences.tsx |
| `frontend/src/features/staff/panels/EmailLogPanel.test.tsx` | 42 | tests EmailLogPanel.tsx |
| `frontend/src/features/staff/panels/OrganizationAnalyticsPanel.test.tsx` | 101 | tests OrganizationAnalyticsPanel.tsx |
| `frontend/src/features/staff/panels/RoleEditorF6.test.tsx` | 37 | imports RoleEditor.tsx, rolesApi.ts |
| `frontend/src/features/staff/panels/StaffInvitations.test.tsx` | 40 | tests StaffInvitations.tsx |
| `frontend/src/features/staff/panels/usersModals/CreateMakerspaceWizard.test.tsx` | 34 | imports forms.ts, CreateMakerspaceModal.tsx, types.ts |
| `frontend/src/features/staff/platformMonitoring.test.tsx` | 91 | imports PlatformDashboardPanel.tsx, TenantUsagePanel.tsx, shared.tsx, staffAccess.ts, staffTabs.ts |

## `dr-screens-ops`

### `dr-screens-ops` — source (142 files)

| path | lines | screen / spec |
|---|---|---|
| `frontend/src/features/forms/CustomAnswersView.tsx` | 36 | via BookingsPanel.tsx (S13) |
| `frontend/src/features/forms/CustomFormBuilder.tsx` | 180 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/notifications/PersonalInbox.tsx` | 71 | via NotificationInbox.tsx (A7) |
| `frontend/src/features/staff/BookableSpaceForm.tsx` | 144 | via BookingsPanel.tsx (S13) |
| `frontend/src/features/staff/BookingDrawer.tsx` | 173 | via BookingsPanel.tsx (S13) |
| `frontend/src/features/staff/BookingsPanel.tsx` | 69 | S13 |
| `frontend/src/features/staff/BroadcastComposer.tsx` | 40 | via NotificationInbox.tsx (A7) |
| `frontend/src/features/staff/CollaborationInbox.tsx` | 75 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventBadgeActions.tsx` | 85 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventCategoriesField.tsx` | 26 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventCertificateActions.tsx` | 29 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventCheckInOperator.tsx` | 32 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventCheckInScanner.tsx` | 182 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventCollaborators.tsx` | 116 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventDrawer.tsx` | 87 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventFeedbackPanel.tsx` | 67 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventFeedbackResponses.tsx` | 27 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventFormFields.tsx` | 75 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventInvitesPanel.tsx` | 26 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventOrganizers.tsx` | 49 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventPromosPanel.tsx` | 30 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventRegisterMember.tsx` | 202 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventRegistrationRoster.tsx` | 83 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventSeriesCollaborationInbox.tsx` | 52 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventSeriesCollaborators.tsx` | 45 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventSeriesDrawer.tsx` | 55 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventSeriesForm.tsx` | 68 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventStaffTicketPicker.tsx` | 10 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventStationSettings.tsx` | 49 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventTicketTemplates.tsx` | 22 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventTicketsPanel.tsx` | 30 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/EventsPanel.tsx` | 110 | S11/S12 |
| `frontend/src/features/staff/ImageUploader.tsx` | 250 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/OfflineCheckInOperator.tsx` | 152 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/StaffBookingForm.tsx` | 66 | via BookingsPanel.tsx (S13) |
| `frontend/src/features/staff/bookingsApi.ts` | 173 | via BookingsPanel.tsx (S13) |
| `frontend/src/features/staff/certificationsApi.ts` | 50 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/deviceQueryKeys.ts` | 5 | via DevicesPanel.tsx (A13/B4) |
| `frontend/src/features/staff/devicesApi.ts` | 29 | via DevicesPanel.tsx (A13/B4) |
| `frontend/src/features/staff/eventCheckInOfflineApi.ts` | 89 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventCheckInOfflineStore.ts` | 123 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventCollaborationsApi.ts` | 97 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventFeedbackApi.ts` | 137 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventSeriesApi.ts` | 126 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventTicketingApi.ts` | 41 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventUi.ts` | 9 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventsApi.ts` | 158 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventsApiTypes.ts` | 120 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventsBadgeApi.ts` | 53 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/eventsRegistrationApi.ts` | 128 | via EventsPanel.tsx (S11/S12) |
| `frontend/src/features/staff/machineConsumablesApi.ts` | 59 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/machineDocumentsApi.ts` | 58 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/machinesApi.ts` | 82 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/machinesApi/keys.ts` | 24 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/machinesApi/logs.ts` | 53 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/machinesApi/machineTypes.ts` | 54 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/machinesApi/machines.ts` | 94 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/machinesApi/types.ts` | 123 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/organizedEventsApi.ts` | 27 | via OrganizedEventsPanel.tsx (A11) |
| `frontend/src/features/staff/panels/AccountabilityPanel.tsx` | 217 | A9 |
| `frontend/src/features/staff/panels/AccountabilityTypes.ts` | 42 | via AccountabilityPanel.tsx (A9) |
| `frontend/src/features/staff/panels/AuditLog.tsx` | 114 | S15 |
| `frontend/src/features/staff/panels/AuditLogFilters.tsx` | 59 | via AuditLog.tsx (S15) |
| `frontend/src/features/staff/panels/AuditVerificationStatus.tsx` | 121 | via AuditLog.tsx (S15) |
| `frontend/src/features/staff/panels/DashboardMachineQueue.tsx` | 38 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/DeviceEnrollmentModal.tsx` | 20 | via DevicesPanel.tsx (A13/B4) |
| `frontend/src/features/staff/panels/DeviceIdentitySection.tsx` | 73 | via DevicesPanel.tsx (A13/B4) |
| `frontend/src/features/staff/panels/DevicesPanel.tsx` | 52 | A13/B4 |
| `frontend/src/features/staff/panels/MachinePublicSettings.tsx` | 84 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/MachineTypesPanel.tsx` | 166 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/MachinesPanel.tsx` | 252 | S10 |
| `frontend/src/features/staff/panels/MemberCardsPanel.tsx` | 152 | A12 |
| `frontend/src/features/staff/panels/NotificationInbox.tsx` | 10 | A7 |
| `frontend/src/features/staff/panels/OperationsReportCharts.tsx` | 83 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportExports.tsx` | 83 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportState.tsx` | 85 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportTable.tsx` | 37 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReports.tsx` | 218 | S14 |
| `frontend/src/features/staff/panels/OperationsReportsBookings.tsx` | 34 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsCoverage.tsx` | 78 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsEvents.tsx` | 35 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsFablab.tsx` | 74 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsFinance.tsx` | 46 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsHardware.tsx` | 82 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsMachineService.tsx` | 75 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsMachineUsage.tsx` | 30 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsMaintenance.tsx` | 36 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsMembers.tsx` | 76 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsParts.tsx` | 4 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsPayments.tsx` | 135 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OperationsReportsPrinterService.tsx` | 71 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/OrganizedEventsPanel.tsx` | 164 | A11 |
| `frontend/src/features/staff/panels/ProblemReportCard.tsx` | 69 | via AccountabilityPanel.tsx (A9) |
| `frontend/src/features/staff/panels/ReportScheduleForm.tsx` | 214 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/ReportSchedules.tsx` | 163 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/SelectedReportPreview.tsx` | 34 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/ServerReportViews.tsx` | 45 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/machine/CapabilityPresetListEditor.tsx` | 70 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/CertificationGrants.tsx` | 48 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/CertificationTypeForm.tsx` | 18 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/CertificationsPanel.tsx` | 32 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/ConsumablePoolCreateForm.tsx` | 151 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/ConsumablesTab.tsx` | 173 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/DocumentsTab.tsx` | 97 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/ErrorsTab.tsx` | 72 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MachineCreateForm.tsx` | 234 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MachineDrawer.tsx` | 133 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MachineReminderPolicy.tsx` | 23 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MachineServiceConsole.tsx` | 162 | B5 |
| `frontend/src/features/staff/panels/machine/MachineTypeCards.tsx` | 109 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MachineTypePage.tsx` | 142 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MaintenanceDocuments.tsx` | 138 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MaintenanceFeedControl.tsx` | 15 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MaintenanceMeterFields.tsx` | 11 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MaintenanceSchedules.tsx` | 213 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MaintenanceTab.tsx` | 266 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/MaterialCataloguePanel.tsx` | 41 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/OperatorsTab.tsx` | 97 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/OverviewTab.tsx` | 147 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/PoolColourSelector.tsx` | 199 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/PoolColourSwatchControl.tsx` | 76 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/PrinterServiceConsole.tsx` | 171 | B5 |
| `frontend/src/features/staff/panels/machine/PublicMachineDisclosure.tsx` | 13 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/SharedConsumablesSection.tsx` | 181 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/UsageTab.tsx` | 78 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/WarrantyTab.tsx` | 5 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/maintenanceApi.ts` | 240 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/serviceDrafts.ts` | 89 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/machine/servicePools.ts` | 54 | via MachinesPanel.tsx (S10) |
| `frontend/src/features/staff/panels/memberCards/CardDialogs.tsx` | 114 | via MemberCardsPanel.tsx (A12) |
| `frontend/src/features/staff/panels/memberCards/CardTemplateForm.tsx` | 165 | via MemberCardsPanel.tsx (A12) |
| `frontend/src/features/staff/panels/memberCards/CardsTable.tsx` | 123 | via MemberCardsPanel.tsx (A12) |
| `frontend/src/features/staff/panels/memberCards/IssueRoster.tsx` | 77 | via MemberCardsPanel.tsx (A12) |
| `frontend/src/features/staff/panels/memberCards/ScanCardBox.tsx` | 114 | via MemberCardsPanel.tsx (A12) |
| `frontend/src/features/staff/panels/memberCards/api.ts` | 152 | via MemberCardsPanel.tsx (A12) |
| `frontend/src/features/staff/panels/memberCards/types.ts` | 81 | via MemberCardsPanel.tsx (A12) |
| `frontend/src/features/staff/panels/operationsReportsConfig.ts` | 51 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/operationsReportsFablabApi.ts` | 87 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/operationsReportsMembersApi.ts` | 42 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/reportSchedulesApi.ts` | 105 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/panels/reportViewsApi.ts` | 26 | via OperationsReports.tsx (S14) |
| `frontend/src/features/staff/staffBookingApi.ts` | 50 | via BookingsPanel.tsx (S13) |

### `dr-screens-ops` — gitignored tests (40 files)

| path | lines | follows |
|---|---|---|
| `frontend/src/features/notifications/PersonalInbox.review.test.tsx` | 43 | tests PersonalInbox.tsx |
| `frontend/src/features/staff/BookableSpaceForm.test.tsx` | 39 | tests BookableSpaceForm.tsx |
| `frontend/src/features/staff/BroadcastComposer.test.tsx` | 28 | tests BroadcastComposer.tsx |
| `frontend/src/features/staff/EventCheckInOperator.test.tsx` | 56 | tests EventCheckInOperator.tsx |
| `frontend/src/features/staff/EventFormFields.test.tsx` | 74 | tests EventFormFields.tsx |
| `frontend/src/features/staff/EventInvitesPanel.test.tsx` | 36 | tests EventInvitesPanel.tsx |
| `frontend/src/features/staff/EventPromosPanel.test.tsx` | 20 | tests EventPromosPanel.tsx |
| `frontend/src/features/staff/EventRegisterMember.test.tsx` | 101 | tests EventRegisterMember.tsx |
| `frontend/src/features/staff/EventRegistrationRoster.test.tsx` | 55 | tests EventRegistrationRoster.tsx |
| `frontend/src/features/staff/EventSeriesForm.test.tsx` | 52 | tests EventSeriesForm.tsx |
| `frontend/src/features/staff/ImageUploader.test.tsx` | 27 | tests ImageUploader.tsx |
| `frontend/src/features/staff/StaffBookingForm.recurring.test.tsx` | 44 | tests StaffBookingForm.tsx |
| `frontend/src/features/staff/StaffBookingForm.test.tsx` | 76 | tests StaffBookingForm.tsx |
| `frontend/src/features/staff/eventCheckInOfflineStore.test.ts` | 67 | tests eventCheckInOfflineStore.ts |
| `frontend/src/features/staff/eventsRegistrationApi.test.tsx` | 30 | tests eventsRegistrationApi.ts |
| `frontend/src/features/staff/panels/AuditLog.test.tsx` | 133 | tests AuditLog.tsx |
| `frontend/src/features/staff/panels/AuditVerificationStatus.test.tsx` | 157 | tests AuditVerificationStatus.tsx |
| `frontend/src/features/staff/panels/DashboardMachineQueue.test.tsx` | 46 | tests DashboardMachineQueue.tsx |
| `frontend/src/features/staff/panels/DevicesPanel.test.tsx` | 114 | tests DevicesPanel.tsx |
| `frontend/src/features/staff/panels/MachineTypesPanel.test.tsx` | 126 | tests MachineTypesPanel.tsx |
| `frontend/src/features/staff/panels/MachinesPanel.test.tsx` | 398 | tests MachinesPanel.tsx |
| `frontend/src/features/staff/panels/MemberCardsPanel.test.tsx` | 151 | tests MemberCardsPanel.tsx |
| `frontend/src/features/staff/panels/NotificationInbox.test.tsx` | 56 | tests NotificationInbox.tsx |
| `frontend/src/features/staff/panels/OperationsReportCharts.test.tsx` | 36 | tests OperationsReportCharts.tsx |
| `frontend/src/features/staff/panels/OperationsReportExports.test.tsx` | 69 | tests OperationsReportExports.tsx |
| `frontend/src/features/staff/panels/OperationsReportsCoverage.test.tsx` | 22 | tests OperationsReportsCoverage.tsx |
| `frontend/src/features/staff/panels/OperationsReportsF6.test.tsx` | 44 | imports OperationsReports.tsx, shared.tsx |
| `frontend/src/features/staff/panels/OperationsReportsFinance.test.tsx` | 29 | tests OperationsReportsFinance.tsx |
| `frontend/src/features/staff/panels/OperationsReportsMembers.test.tsx` | 58 | tests OperationsReportsMembers.tsx |
| `frontend/src/features/staff/panels/OrganizedEventsPanel.test.tsx` | 205 | tests OrganizedEventsPanel.tsx |
| `frontend/src/features/staff/panels/ReportScheduleRules.test.tsx` | 54 | imports ReportScheduleForm.tsx, operationsReportsConfig.ts, reportSchedulesApi.ts |
| `frontend/src/features/staff/panels/ReportSchedules.test.tsx` | 144 | tests ReportSchedules.tsx |
| `frontend/src/features/staff/panels/SelectedReportPreview.test.tsx` | 23 | tests SelectedReportPreview.tsx |
| `frontend/src/features/staff/panels/ServerReportViews.test.tsx` | 55 | tests ServerReportViews.tsx |
| `frontend/src/features/staff/panels/machine/CertificationsPanel.test.tsx` | 60 | tests CertificationsPanel.tsx |
| `frontend/src/features/staff/panels/machine/ConsumablePoolCreateForm.test.tsx` | 157 | tests ConsumablePoolCreateForm.tsx |
| `frontend/src/features/staff/panels/machine/MachineCreateForm.test.tsx` | 109 | tests MachineCreateForm.tsx |
| `frontend/src/features/staff/panels/machine/MachineServiceConsole.test.tsx` | 42 | tests MachineServiceConsole.tsx |
| `frontend/src/features/staff/panels/machine/PrinterServiceConsole.test.tsx` | 69 | tests PrinterServiceConsole.tsx |
| `frontend/src/features/staff/panels/machine/SharedConsumablesSection.test.tsx` | 81 | tests SharedConsumablesSection.tsx |

## `dr-screens-public`

Also owns, outside the counted universe: `frontend/public/member-pwa/offline.html` + `offline.js` (I4; `offline.css` colours were done in wave 1 `dr-brand-assets`).

### `dr-screens-public` — source (147 files)

| path | lines | screen / spec |
|---|---|---|
| `frontend/src/App.tsx` | 53 | F7/F10 (tenant loading/unavailable) + kiosk route |
| `frontend/src/AppRoutes.tsx` | 136 | F6/F7/F10 (NotFound, RouteFallback, FamilyHome) |
| `frontend/src/features/AboutPage.tsx` | 73 | G2 |
| `frontend/src/features/LandingPage.tsx` | 173 | G1 |
| `frontend/src/features/auth/LegacyPasswordResetForm.tsx` | 61 | via ResetPasswordPage.tsx (E5) |
| `frontend/src/features/auth/MfaFlow.tsx` | 47 | F2 |
| `frontend/src/features/auth/NewPasswordFields.tsx` | 66 | via ResetPasswordPage.tsx (E5) |
| `frontend/src/features/auth/PasswordRecoveryFlow.tsx` | 168 | via ResetPasswordPage.tsx (E5) |
| `frontend/src/features/auth/SocialSignInButtons.tsx` | 153 | via LoginPanel.tsx (S20) |
| `frontend/src/features/auth/StaffInvitationAcceptPage.tsx` | 26 | S22 |
| `frontend/src/features/auth/mfaApi.ts` | 26 | via MemberAuthPanel.tsx (S21) |
| `frontend/src/features/auth/passwordRecovery.ts` | 41 | via ResetPasswordPage.tsx (E5) |
| `frontend/src/features/auth/socialSdk.ts` | 193 | via LoginPanel.tsx (S20) |
| `frontend/src/features/bookings/AvailabilityCalendar.tsx` | 76 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/bookings/BookingCalendar.tsx` | 20 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/bookings/BookingReschedule.tsx` | 23 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/bookings/MyBookings.tsx` | 87 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/bookings/PublicBookingForm.tsx` | 113 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/bookings/PublicBookingsPage.tsx` | 129 | G4 |
| `frontend/src/features/bookings/SpaceDiscoveryCalendar.tsx` | 33 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/bookings/publicBookingsApi.ts` | 91 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/discovery/DiscoveryControls.tsx` | 26 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/discovery/MonthCalendar.tsx` | 33 | via PublicEventsPage.tsx (G5) |
| `frontend/src/features/discovery/calendarDates.ts` | 40 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/discovery/useDiscoveryState.ts` | 22 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/events/EventCheckInStationPage.tsx` | 53 | I1 |
| `frontend/src/features/events/EventContactFallback.tsx` | 9 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/events/EventPrice.tsx` | 12 | via PublicEventDetailPage.tsx (S19) |
| `frontend/src/features/events/EventTicketPicker.tsx` | 16 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/events/eventCalendar.ts` | 12 | via PublicEventDetailPage.tsx (S19) |
| `frontend/src/features/events/eventTicketTypes.ts` | 20 | via PublicEventDetailPage.tsx (S19) |
| `frontend/src/features/forms/CustomFormFields.tsx` | 91 | via PublicEventFeedbackPage.tsx (G9) |
| `frontend/src/features/forms/customFormTypes.ts` | 78 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/inventory/AvailabilityBadge.tsx` | 68 | via PublicItemPage.tsx (S18) |
| `frontend/src/features/inventory/BorrowRequestCard.tsx` | 203 | via PublicInventoryPage.tsx (S17) |
| `frontend/src/features/inventory/EventRegistrationForm.tsx` | 109 | via PublicEventDetailPage.tsx (S19) |
| `frontend/src/features/inventory/MachineIntakeForm.tsx` | 41 | via PublicMachinesPage.tsx (G3) |
| `frontend/src/features/inventory/NotifyWhenBack.tsx` | 25 | via PublicItemPage.tsx (S18) |
| `frontend/src/features/inventory/ProductCard.tsx` | 136 | via PublicInventoryPage.tsx (S17) |
| `frontend/src/features/inventory/ProductQuickViewModal.tsx` | 94 | via PublicInventoryPage.tsx (S17) |
| `frontend/src/features/inventory/PublicEventDetailPage.tsx` | 54 | S19 |
| `frontend/src/features/inventory/PublicEventFeedbackPage.tsx` | 74 | G9 |
| `frontend/src/features/inventory/PublicEventsPage.tsx` | 151 | G5 |
| `frontend/src/features/inventory/PublicEvidenceUpload.tsx` | 102 | via PublicSelfCheckoutPage.tsx (G10) |
| `frontend/src/features/inventory/PublicInventoryPage.tsx` | 201 | S17 |
| `frontend/src/features/inventory/PublicInventoryParts.tsx` | 149 | via PublicBookingsPage.tsx (G4) |
| `frontend/src/features/inventory/PublicItemPage.tsx` | 65 | S18 |
| `frontend/src/features/inventory/PublicMachinesPage.tsx` | 139 | G3 |
| `frontend/src/features/inventory/PublicRequestPanel.tsx` | 266 | via PublicInventoryPage.tsx (S17) |
| `frontend/src/features/inventory/PublicSelfCheckoutPage.tsx` | 259 | G10 |
| `frontend/src/features/inventory/PublicToolResultCard.tsx` | 31 | via PublicSelfCheckoutPage.tsx (G10) |
| `frontend/src/features/inventory/PublicToolScanPanel.tsx` | 207 | via PublicInventoryPage.tsx (S17) |
| `frontend/src/features/inventory/api.ts` | 144 | via AppRoutes.tsx (F6/F7/F10 (NotFound, RouteFallback, FamilyHome)) |
| `frontend/src/features/inventory/publicInventory/PublicInventoryHeader.tsx` | 92 | via PublicInventoryPage.tsx (S17) |
| `frontend/src/features/inventory/publicInventory/useInventoryCart.ts` | 64 | via PublicInventoryPage.tsx (S17) |
| `frontend/src/features/inventory/selfCheckoutApi.ts` | 94 | via PublicSelfCheckoutPage.tsx (G10) |
| `frontend/src/features/inventory/usePublicInventory.ts` | 50 | via AppRoutes.tsx (F6/F7/F10 (NotFound, RouteFallback, FamilyHome)) |
| `frontend/src/features/kiosk/KioskOfflineHandover.tsx` | 85 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/KioskOnlineHandover.tsx` | 93 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/KioskOnlineScanner.tsx` | 31 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/KioskQueueStatus.tsx` | 27 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/KioskReplayCorrection.tsx` | 108 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/KioskReplayDetail.tsx` | 32 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/KioskStationPage.tsx` | 107 | S23 |
| `frontend/src/features/kiosk/PublicDeskKioskPage.tsx` | 33 | I2 |
| `frontend/src/features/kiosk/ScannerPage.tsx` | 77 | I3 |
| `frontend/src/features/kiosk/kioskApi.ts` | 93 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/kioskReplayApi.ts` | 86 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/kioskReplayClient.ts` | 83 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/kioskSession.ts` | 49 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/offlineEvidence.ts` | 31 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/offlineQueueDb.ts` | 59 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/offlineQueueStore.ts` | 141 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/offlineQueueTypes.ts` | 44 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/offlineTestFixtures.ts` | 25 | test fixture (kiosk tests) |
| `frontend/src/features/kiosk/recoveryTestFixtures.ts` | 14 | test fixture (kiosk tests) |
| `frontend/src/features/kiosk/replayCorrectionCapture.ts` | 44 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/replayPolicy.ts` | 32 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/replayRecoveryGuidance.ts` | 40 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/useKioskQueue.ts` | 103 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/kiosk/useKioskReplays.ts` | 48 | via KioskStationPage.tsx (S23) |
| `frontend/src/features/members/AdmissionJoin.tsx` | 39 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/ArchivedPayments.tsx` | 160 | G11 |
| `frontend/src/features/members/InvitationRequestForm.tsx` | 91 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/JoinMembershipCta.tsx` | 42 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberAccountExports.tsx` | 24 | via MemberAccountPage.tsx (C6) |
| `frontend/src/features/members/MemberAccountMembership.tsx` | 27 | via MemberAccountPage.tsx (C6) |
| `frontend/src/features/members/MemberAccountPage.tsx` | 52 | C6 |
| `frontend/src/features/members/MemberAccountProfile.tsx` | 27 | via MemberAccountPage.tsx (C6) |
| `frontend/src/features/members/MemberAccountSessions.tsx` | 26 | via MemberAccountPage.tsx (C6) |
| `frontend/src/features/members/MemberActivity.tsx` | 156 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberAdmission.tsx` | 47 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberArea.tsx` | 199 | S16/H1-H6 |
| `frontend/src/features/members/MemberAuthPanel.tsx` | 241 | S21 |
| `frontend/src/features/members/MemberCalendarActions.tsx` | 89 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberCardPanel.tsx` | 115 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberCertifications.tsx` | 22 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberClaimRedemption.tsx` | 27 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberClaimSession.tsx` | 44 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberDashboardSections.tsx` | 136 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberDirectory.tsx` | 210 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberEventCancel.tsx` | 31 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberEventFeedback.tsx` | 69 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberInstall.tsx` | 25 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberLoanRenew.tsx` | 22 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberPayments.tsx` | 102 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberProfilePanel.tsx` | 245 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberReferrals.tsx` | 105 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/MemberVerifierPanel.tsx` | 23 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/PartnerEvents.tsx` | 233 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/geolocation.ts` | 29 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberAccountApi.ts` | 18 | via MemberAccountPage.tsx (C6) |
| `frontend/src/features/members/memberCard/CardPhotoUpload.tsx` | 133 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberCard/OfflineCardSave.tsx` | 31 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberCard/OfflineLoansControl.tsx` | 24 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberCard/api.ts` | 98 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberCard/offlineCard.ts` | 40 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberCard/offlineLoans.ts` | 32 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberProfile/Field.tsx` | 21 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberProfile/ProjectEditor.tsx` | 105 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberProfile/helpers.ts` | 16 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/memberProfile/types.ts` | 38 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/members/membershipAdmissionApi.ts` | 48 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/notifications/AnnouncementFeed.tsx` | 20 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/notifications/MemberNotifications.tsx` | 14 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/notifications/PreferenceCentre.tsx` | 37 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/notifications/personalQueryKeys.ts` | 17 | via MemberArea.tsx (S16/H1-H6) |
| `frontend/src/features/organizations/OrganizationInvitationRedeemPage.tsx` | 92 | S22/F5 |
| `frontend/src/features/organizations/PublicOrganizationPage.tsx` | 119 | G8 |
| `frontend/src/features/organizations/publicOrganizationsApi.ts` | 61 | via PublicOrganizationPage.tsx (G8) |
| `frontend/src/features/printing/PublicPrintRequestForm.tsx` | 237 | via PublicPrintRequestPage.tsx (G6) |
| `frontend/src/features/printing/PublicPrintRequestPage.tsx` | 61 | G6 |
| `frontend/src/features/printing/PublicPrintRequestPanels.tsx` | 10 | via PublicPrintRequestPage.tsx (G6) |
| `frontend/src/features/printing/PublicPrintRequestParts.tsx` | 269 | via PublicPrintRequestPage.tsx (G6) |
| `frontend/src/features/printing/PublicPrintUploads.ts` | 35 | via PublicPrintRequestPage.tsx (G6) |
| `frontend/src/features/printing/publicApi.ts` | 42 | via PublicPrintRequestPage.tsx (G6) |
| `frontend/src/features/staff/ChangePasswordGate.tsx` | 97 | F1 |
| `frontend/src/features/staff/LoginPanel.tsx` | 125 | S20 |
| `frontend/src/features/staff/PlatformApps.tsx` | 6 | via AppRoutes.tsx (F6/F7/F10 (NotFound, RouteFallback, FamilyHome)) |
| `frontend/src/features/staff/RecoveryQuarantinePanel.tsx` | 46 | F4 |
| `frontend/src/features/staff/ResetPasswordPage.tsx` | 22 | E5 |
| `frontend/src/features/staff/StaffAccessDenied.tsx` | 24 | F3 |
| `frontend/src/features/staff/StaffPanelErrorBoundary.tsx` | 44 | F9 |
| `frontend/src/features/stats/PublicStatsPage.tsx` | 137 | G7 |
| `frontend/src/features/stats/StatsParts.tsx` | 113 | via PublicStatsPage.tsx (G7) |
| `frontend/src/features/stats/StatsSections.tsx` | 255 | via PublicStatsPage.tsx (G7) |
| `frontend/src/features/stats/api.ts` | 87 | via PublicStatsPage.tsx (G7) |

### `dr-screens-public` — gitignored tests (77 files)

| path | lines | follows |
|---|---|---|
| `frontend/src/App.centralMemberRoute.test.tsx` | 81 | tests App.tsx |
| `frontend/src/App.kioskOffline.test.tsx` | 17 | tests App.tsx |
| `frontend/src/AppRoutes.familyHome.test.tsx` | 82 | tests AppRoutes.tsx |
| `frontend/src/AppRoutesPublic.test.tsx` | 99 | imports AppRoutes.tsx |
| `frontend/src/features/auth/MfaFlow.test.tsx` | 55 | tests MfaFlow.tsx |
| `frontend/src/features/auth/PasswordRecoveryFlow.test.tsx` | 142 | tests PasswordRecoveryFlow.tsx |
| `frontend/src/features/auth/SocialSignInButtons.test.tsx` | 117 | tests SocialSignInButtons.tsx |
| `frontend/src/features/auth/StaffInvitationAcceptPage.test.tsx` | 44 | tests StaffInvitationAcceptPage.tsx |
| `frontend/src/features/bookings/BookingCalendar.test.tsx` | 26 | tests BookingCalendar.tsx |
| `frontend/src/features/bookings/BookingReschedule.test.tsx` | 29 | tests BookingReschedule.tsx |
| `frontend/src/features/bookings/MyBookings.test.tsx` | 88 | tests MyBookings.tsx |
| `frontend/src/features/bookings/SpaceDiscoveryCalendar.test.tsx` | 41 | tests SpaceDiscoveryCalendar.tsx |
| `frontend/src/features/discovery/PublicDiscovery.test.tsx` | 109 | imports PublicBookingsPage.tsx, PublicEventsPage.tsx |
| `frontend/src/features/discovery/calendarDates.test.tsx` | 36 | tests calendarDates.ts |
| `frontend/src/features/events/EventPrice.test.tsx` | 20 | tests EventPrice.tsx |
| `frontend/src/features/events/EventTicketPicker.test.tsx` | 18 | tests EventTicketPicker.tsx |
| `frontend/src/features/inventory/MachineIntakeForm.test.tsx` | 41 | tests MachineIntakeForm.tsx |
| `frontend/src/features/inventory/NotifyWhenBack.test.tsx` | 36 | tests NotifyWhenBack.tsx |
| `frontend/src/features/inventory/ProductCard.test.tsx` | 16 | tests ProductCard.tsx |
| `frontend/src/features/inventory/PublicEventDetailPage.test.tsx` | 110 | tests PublicEventDetailPage.tsx |
| `frontend/src/features/inventory/PublicEventsPage.test.tsx` | 76 | tests PublicEventsPage.tsx |
| `frontend/src/features/inventory/PublicInventoryBranding.test.tsx` | 73 | imports PublicInventoryPage.tsx |
| `frontend/src/features/inventory/PublicMachinesPage.test.tsx` | 35 | tests PublicMachinesPage.tsx |
| `frontend/src/features/inventory/PublicRequestPanelAccountLess.test.tsx` | 246 | imports PublicRequestPanel.tsx, api.ts |
| `frontend/src/features/kiosk/KioskOnlineHandover.test.tsx` | 31 | tests KioskOnlineHandover.tsx |
| `frontend/src/features/kiosk/KioskReplayCorrection.test.tsx` | 81 | tests KioskReplayCorrection.tsx |
| `frontend/src/features/kiosk/KioskStationPage.offline.test.tsx` | 52 | tests KioskStationPage.tsx |
| `frontend/src/features/kiosk/KioskStationPage.test.tsx` | 100 | tests KioskStationPage.tsx |
| `frontend/src/features/kiosk/kioskReplayApi.test.ts` | 38 | tests kioskReplayApi.ts |
| `frontend/src/features/kiosk/kioskReplayClient.test.ts` | 119 | tests kioskReplayClient.ts |
| `frontend/src/features/kiosk/kioskSession.test.ts` | 21 | tests kioskSession.ts |
| `frontend/src/features/kiosk/offlineEvidence.test.ts` | 34 | tests offlineEvidence.ts |
| `frontend/src/features/kiosk/offlineQueueStore.test.ts` | 95 | tests offlineQueueStore.ts |
| `frontend/src/features/kiosk/recoveryQueuePersistence.test.ts` | 22 | imports offlineQueueDb.ts, offlineQueueStore.ts, offlineTestFixtures.ts, recoveryTestFixtures.ts |
| `frontend/src/features/kiosk/replayCorrectionCapture.test.ts` | 46 | tests replayCorrectionCapture.ts |
| `frontend/src/features/kiosk/replayRecoveryGuidance.test.ts` | 11 | tests replayRecoveryGuidance.ts |
| `frontend/src/features/kiosk/useKioskQueue.test.tsx` | 48 | tests useKioskQueue.ts |
| `frontend/src/features/members/AdmissionJoin.test.tsx` | 47 | tests AdmissionJoin.tsx |
| `frontend/src/features/members/ArchivedPayments.test.tsx` | 85 | tests ArchivedPayments.tsx |
| `frontend/src/features/members/InvitationRequestForm.test.tsx` | 69 | tests InvitationRequestForm.tsx |
| `frontend/src/features/members/JoinMembershipCta.test.tsx` | 34 | tests JoinMembershipCta.tsx |
| `frontend/src/features/members/MemberAccount.test.tsx` | 117 | imports MemberAccountExports.tsx, MemberAccountMembership.tsx, MemberAccountPage.tsx, MemberAccountProfile.tsx, MemberAccountSes |
| `frontend/src/features/members/MemberActivity.test.tsx` | 64 | tests MemberActivity.tsx |
| `frontend/src/features/members/MemberAdmission.test.tsx` | 42 | tests MemberAdmission.tsx |
| `frontend/src/features/members/MemberArea.moduleGates.test.tsx` | 70 | tests MemberArea.tsx |
| `frontend/src/features/members/MemberArea.test.tsx` | 75 | tests MemberArea.tsx |
| `frontend/src/features/members/MemberAreaAdmission.test.tsx` | 64 | imports MemberArea.tsx |
| `frontend/src/features/members/MemberAreaArchivedLink.test.tsx` | 96 | imports MemberArea.tsx |
| `frontend/src/features/members/MemberAreaBranding.test.tsx` | 53 | imports MemberArea.tsx |
| `frontend/src/features/members/MemberAreaPortal.test.tsx` | 185 | imports MemberArea.tsx |
| `frontend/src/features/members/MemberCardPanel.test.tsx` | 156 | tests MemberCardPanel.tsx |
| `frontend/src/features/members/MemberCertifications.test.tsx` | 28 | tests MemberCertifications.tsx |
| `frontend/src/features/members/MemberClaimRedemption.test.tsx` | 22 | tests MemberClaimRedemption.tsx |
| `frontend/src/features/members/MemberClaimSession.test.tsx` | 25 | tests MemberClaimSession.tsx |
| `frontend/src/features/members/MemberDashboardSections.test.tsx` | 38 | tests MemberDashboardSections.tsx |
| `frontend/src/features/members/MemberDirectory.test.tsx` | 35 | tests MemberDirectory.tsx |
| `frontend/src/features/members/MemberEventCancel.test.tsx` | 72 | tests MemberEventCancel.tsx |
| `frontend/src/features/members/MemberInvitationAdmission.test.tsx` | 31 | imports MemberReferrals.tsx |
| `frontend/src/features/members/MemberLoanRenew.test.tsx` | 60 | tests MemberLoanRenew.tsx |
| `frontend/src/features/members/MemberPayments.test.tsx` | 59 | tests MemberPayments.tsx |
| `frontend/src/features/members/MemberProfilePanel.test.tsx` | 22 | tests MemberProfilePanel.tsx |
| `frontend/src/features/members/MemberReferrals.test.tsx` | 98 | tests MemberReferrals.tsx |
| `frontend/src/features/members/MemberVerifierPanel.test.tsx` | 20 | tests MemberVerifierPanel.tsx |
| `frontend/src/features/members/PartnerEventsTicketing.test.tsx` | 31 | imports PartnerEvents.tsx |
| `frontend/src/features/members/geolocation.test.ts` | 30 | tests geolocation.ts |
| `frontend/src/features/members/memberCard/OfflineCardSave.test.tsx` | 61 | tests OfflineCardSave.tsx |
| `frontend/src/features/members/memberCard/OfflineLoansControl.test.tsx` | 31 | tests OfflineLoansControl.tsx |
| `frontend/src/features/members/memberCard/offlineCard.test.ts` | 22 | tests offlineCard.ts |
| `frontend/src/features/members/memberCard/offlineLoans.test.ts` | 35 | tests offlineLoans.ts |
| `frontend/src/features/members/memberCard/offlineShell.test.ts` | 35 | tests public/member-pwa/offline.js (I4) |
| `frontend/src/features/notifications/PreferenceCentre.digest.test.tsx` | 20 | tests PreferenceCentre.tsx |
| `frontend/src/features/notifications/personalQueryKeys.test.ts` | 23 | tests personalQueryKeys.ts |
| `frontend/src/features/organizations/PublicOrganizationPage.test.tsx` | 25 | tests PublicOrganizationPage.tsx |
| `frontend/src/features/printing/PublicPrintRequestForm.test.tsx` | 67 | tests PublicPrintRequestForm.tsx |
| `frontend/src/features/printing/publicApi.test.ts` | 17 | tests publicApi.ts |
| `frontend/e2e/auth.spec.ts` | 20 | staff sign-in S20 |
| `frontend/e2e/public-visibility.spec.ts` | 27 | public catalogue S17 |

## 2. FROZEN (no wave-3 edits)

Owned by wave 2 (`dr-primitives`, `dr-layouts`, `dr-shell`) or gating/wiring. Wave-3 lanes import them, never edit them.

### FROZEN — source (18 files)

| path | lines | reason |
|---|---|---|
| `frontend/src/features/members/MemberPortalTabs.tsx` | 54 | gating (member tabs) |
| `frontend/src/features/staff/CommandPalette.tsx` | 86 | wave-2 dr-shell (J1) |
| `frontend/src/features/staff/SetupChecklist.tsx` | 24 | wave-2 dr-shell (J3) |
| `frontend/src/features/staff/StaffApp.tsx` | 175 | wiring (wave-2 dr-shell) |
| `frontend/src/features/staff/StaffDock.tsx` | 234 | wave-2 dr-shell (replaced) |
| `frontend/src/features/staff/StaffDockPopover.tsx` | 115 | wave-2 dr-shell (StaffDock dep) |
| `frontend/src/features/staff/StaffHeader.tsx` | 86 | wave-2 dr-shell (replaced) |
| `frontend/src/features/staff/StaffPlatformTabContent.tsx` | 55 | wiring (tab dispatch) |
| `frontend/src/features/staff/StaffTabContent.tsx` | 223 | wiring (wave-2 dr-shell) |
| `frontend/src/features/staff/StaffTabLoaders.tsx` | 47 | wiring (lazy tab loaders) |
| `frontend/src/features/staff/StaffWorkspace.tsx` | 190 | wiring (wave-2 dr-shell) |
| `frontend/src/features/staff/setupChecklistState.ts` | 10 | wave-2 dr-shell (J3 state) |
| `frontend/src/features/staff/staffAccess.ts` | 205 | gating |
| `frontend/src/features/staff/staffNavIcons.tsx` | 96 | wave-2 dr-shell (nav icons) |
| `frontend/src/features/staff/staffTabs.ts` | 249 | gating |
| `frontend/src/features/staff/useDockAnchor.ts` | 45 | wave-2 dr-shell (StaffDock dep) |
| `frontend/src/features/staff/useStaffSession.ts` | 224 | session wiring |
| `frontend/src/features/staff/useUnreadNotifications.ts` | 20 | wave-2 dr-shell (unread badge, W31) |

### FROZEN — tests (13 files)

| path | lines | follows |
|---|---|---|
| `frontend/src/features/members/MemberPortalTabs.test.tsx` | 59 | tests MemberPortalTabs.tsx |
| `frontend/src/features/staff/CommandPalette.test.tsx` | 81 | tests CommandPalette.tsx |
| `frontend/src/features/staff/SetupChecklist.test.tsx` | 35 | tests SetupChecklist.tsx |
| `frontend/src/features/staff/StaffApp.platform.test.tsx` | 38 | tests StaffApp.tsx |
| `frontend/src/features/staff/StaffDock.test.tsx` | 154 | tests StaffDock.tsx |
| `frontend/src/features/staff/devicesTab.test.ts` | 22 | imports staffAccess.ts, staffTabs.ts |
| `frontend/src/features/staff/memberCardsTab.test.ts` | 36 | imports staffAccess.ts, staffTabs.ts |
| `frontend/src/features/staff/organizationAnalyticsTab.test.tsx` | 75 | imports StaffTabContent.tsx, staffAccess.ts, staffTabs.ts |
| `frontend/src/features/staff/organizationGovernanceTab.test.ts` | 21 | imports staffAccess.ts, staffTabs.ts |
| `frontend/src/features/staff/staffTabs.familyOnly.test.ts` | 35 | tests staffTabs.ts |
| `frontend/src/features/staff/staffTabs.moduleGates.test.ts` | 84 | tests staffTabs.ts |
| `frontend/src/features/staff/staffTabs.test.ts` | 222 | tests staffTabs.ts |
| `frontend/e2e/helpers.ts` | 109 | wave-2 dr-shell owns e2e helper updates (shell-contracts §2.2) |

Out-of-universe FROZEN globs (not counted in the total; outside `features/` or created by wave 2):

- `frontend/src/components/ui/**`
- `frontend/src/components/layouts/** (created by dr-layouts)`
- `frontend/src/components/shell/** (created by dr-shell)`
- `frontend/src/lib/features.ts`
- `frontend/src/lib/publicHome.ts`
- `frontend/src/features/staff/sidebarSections.ts (created by dr-shell; must be added to this FROZEN list once it exists)`
- `frontend/src/features/staff/StaffWorkspace.routing.test.tsx, StaffApp.shell.test.tsx, Sidebar.test.tsx (created by dr-shell)`

## 3. Coordinator

No lane edits these. Claude applies any change at merge, after the owning lanes land.

### Coordinator — shared source (3+ lanes or imported by FROZEN wiring) (7 files)

| path | lines | why shared |
|---|---|---|
| `frontend/src/features/staff/ListViewControls.tsx` | 15 | saved-view/list toolbar used by desk, admin, ops |
| `frontend/src/features/staff/SavedViewsMenu.tsx` | 53 | used by ListViewControls (desk/admin/ops) and InventoryWorkspace (inventory) |
| `frontend/src/features/staff/StaffListContext.tsx` | 3 | list context provided by FROZEN StaffWorkspace; consumed by desk/admin/ops/inventory |
| `frontend/src/features/staff/StaffPanels.tsx` | 19 | re-export barrel of screens from 4 lanes + Panel/useStaffGet |
| `frontend/src/features/staff/panels/shared.tsx` | 122 | Panel/useStaffGet/types; imported by FROZEN StaffTabContent and all 4 staff lanes |
| `frontend/src/features/staff/queryInvalidation.ts` | 47 | query-key invalidation used by desk, inventory, ops, public |
| `frontend/src/features/staff/quickCreate.ts` | 23 | quick-create intents used by desk, inventory, ops |

### Coordinator — cross-lane tests and e2e specs (8 files)

| path | lines | spans |
|---|---|---|
| `frontend/src/features/forms/FeedbackFormControls.test.tsx` | 43 | imports CustomFormBuilder.tsx, CustomFormFields.tsx, customFormTypes.ts |
| `frontend/src/features/notifications/NotificationControls.test.tsx` | 77 | imports DeliveryLogScreen.tsx, PreferenceCentre.tsx |
| `frontend/src/features/staff/PaymentBilling.test.tsx` | 79 | imports MemberPayments.tsx, PaymentRefundDialog.tsx, PaymentsPanel.tsx, RefundReceiptAmendDialog.tsx, paymentsApi.ts |
| `frontend/src/features/staff/SavedViewsMenu.test.tsx` | 60 | tests SavedViewsMenu.tsx |
| `frontend/src/features/staff/Track3Payments.test.tsx` | 101 | imports BookableSpaceForm.tsx, MakerspaceMembershipSettings.tsx, PaymentReconcileActions.tsx, StaffPanels.tsx |
| `frontend/src/features/staff/quickCreate.test.ts` | 13 | tests quickCreate.ts |
| `frontend/e2e/a11y.spec.ts` | 93 | spans public catalogue, staff login, requests, events, bookings, member area |
| `frontend/e2e/offline-handover.spec.ts` | 142 | spans kiosk station (public) + Failed kiosk handovers recovery in Requests (desk) |

### Needs wave-3 coordinator edit (FROZEN files a wave-3 screen may need; listed above, not recounted)

| FROZEN file | requesting lane | why |
|---|---|---|
| `frontend/src/features/staff/StaffTabContent.tsx` | `dr-screens-public` | F8 "No space assigned yet" card lives inline (`Panel title="No makerspace"`) |
| `frontend/src/features/staff/StaffApp.tsx` | `dr-screens-public` | F7 `StaffLoading` ("Restoring your session…") lives inline |
| `frontend/src/features/staff/SetupChecklist.tsx` | `dr-screens-desk` | J3 placement must be coordinated with the S1 Dashboard |
| `frontend/src/features/members/MemberPortalTabs.tsx` | `dr-screens-public` | H1–H6 tab labels/counts if the member tab bodies need them |
| `frontend/src/features/staff/StaffTabLoaders.tsx` | `any` | only if a lane renames or moves a panel's export (lane must report it) |
| `frontend/src/features/staff/staffTabs.ts` | `dr-screens-desk` | only if the S2 request-tab URL contract (shell-contracts §3, PLAN §10.3) needs a path helper |

## 4. Consumes unchanged

Lane-owned files imported by another lane's screens. The consumer may import them but must not edit them; it asks the owner (or the coordinator at merge) for a change.

| path | owner | consumed unchanged by | via |
|---|---|---|---|
| `frontend/src/features/auth/MfaAccountPage.tsx` | `dr-screens-admin` | `dr-screens-public` | AppRoutes.tsx |
| `frontend/src/features/auth/MfaFlow.tsx` | `dr-screens-public` | `dr-screens-admin` | MfaAccountPage.tsx |
| `frontend/src/features/auth/mfaApi.ts` | `dr-screens-public` | `dr-screens-admin` | MfaAccountPage.tsx |
| `frontend/src/features/forms/CustomAnswersView.tsx` | `dr-screens-ops` | `dr-screens-admin` | MembershipAdmissionReview.tsx |
| `frontend/src/features/forms/CustomAnswersView.tsx` | `dr-screens-ops` | `dr-screens-public` | MemberAdmission.tsx |
| `frontend/src/features/forms/CustomFormBuilder.tsx` | `dr-screens-ops` | `dr-screens-admin` | MembershipAdmissionSettings.tsx |
| `frontend/src/features/forms/CustomFormFields.tsx` | `dr-screens-public` | `dr-screens-desk` | WalkInMemberForm.tsx |
| `frontend/src/features/forms/CustomFormFields.tsx` | `dr-screens-public` | `dr-screens-ops` | EventRegisterMember.tsx, StaffBookingForm.tsx |
| `frontend/src/features/forms/customFormTypes.ts` | `dr-screens-public` | `dr-screens-desk` | WalkInMemberForm.tsx |
| `frontend/src/features/forms/customFormTypes.ts` | `dr-screens-public` | `dr-screens-ops` | BookableSpaceForm.tsx, CustomAnswersView.tsx, CustomFormBuilder.tsx, EventFeedbackPanel.tsx, EventRegisterMember.tsx, StaffBookingForm.tsx, bookingsApi.ts, eventFeedbackApi.ts, eventSeriesApi.ts, eventsApiTypes.ts, staffBookingApi.ts |
| `frontend/src/features/inventory/KitChecklist.tsx` | `dr-screens-desk` | `dr-screens-inventory` | ContainersPanel.tsx, InventoryPanelShared.ts, InventoryWorkspace.tsx |
| `frontend/src/features/inventory/KitChecklist.tsx` | `dr-screens-desk` | `dr-screens-public` | KioskOfflineHandover.tsx, KioskOnlineHandover.tsx, PublicSelfCheckoutPage.tsx, kioskApi.ts, selfCheckoutApi.ts |
| `frontend/src/features/kiosk/KioskReplayDetail.tsx` | `dr-screens-public` | `dr-screens-desk` | KioskReplayRecoveryPanel.tsx |
| `frontend/src/features/kiosk/useKioskReplays.ts` | `dr-screens-public` | `dr-screens-desk` | KioskReplayRecoveryPanel.tsx, KioskReplayResolution.tsx |
| `frontend/src/features/members/membershipAdmissionApi.ts` | `dr-screens-public` | `dr-screens-admin` | MembersPanel.tsx, MembershipAdmissionReview.tsx, MembershipAdmissionSettings.tsx |
| `frontend/src/features/members/membershipAdmissionApi.ts` | `dr-screens-public` | `dr-screens-desk` | WalkInMemberForm.tsx |
| `frontend/src/features/notifications/PersonalInbox.tsx` | `dr-screens-ops` | `dr-screens-admin` | DeliveryLogScreen.tsx, SuppressionAdmin.tsx |
| `frontend/src/features/notifications/PersonalInbox.tsx` | `dr-screens-ops` | `dr-screens-public` | MemberNotifications.tsx |
| `frontend/src/features/notifications/personalQueryKeys.ts` | `dr-screens-public` | `dr-screens-ops` | PersonalInbox.tsx |
| `frontend/src/features/organizations/publicOrganizationsApi.ts` | `dr-screens-public` | `dr-screens-admin` | organizationsApi.ts |
| `frontend/src/features/payments/PaymentDocuments.tsx` | `dr-screens-desk` | `dr-screens-public` | MemberPayments.tsx |
| `frontend/src/features/staff/ImageUploader.tsx` | `dr-screens-ops` | `dr-screens-admin` | MakerspaceBrandingSettings.tsx |
| `frontend/src/features/staff/ImageUploader.tsx` | `dr-screens-ops` | `dr-screens-inventory` | InventoryWorkspace.tsx |
| `frontend/src/features/staff/ImageUploader.tsx` | `dr-screens-ops` | `dr-screens-public` | MemberProfilePanel.tsx, ProjectEditor.tsx |
| `frontend/src/features/staff/NotificationRecipientPicker.tsx` | `dr-screens-admin` | `dr-screens-ops` | MachinesPanel.tsx |
| `frontend/src/features/staff/OfflineCheckInOperator.tsx` | `dr-screens-ops` | `dr-screens-public` | EventCheckInStationPage.tsx |
| `frontend/src/features/staff/PaymentDueBadge.tsx` | `dr-screens-desk` | `dr-screens-public` | MemberPayments.tsx |
| `frontend/src/features/staff/PaymentReconcileActions.tsx` | `dr-screens-desk` | `dr-screens-admin` | MembersPanel.tsx, MembershipAdmissionReview.tsx |
| `frontend/src/features/staff/PaymentReconcileActions.tsx` | `dr-screens-desk` | `dr-screens-ops` | BookingDrawer.tsx, EventRegistrationRoster.tsx, bookingsApi.ts, eventsApiTypes.ts |
| `frontend/src/features/staff/WarrantySection.tsx` | `dr-screens-inventory` | `dr-screens-ops` | WarrantyTab.tsx |
| `frontend/src/features/staff/eventCheckInOfflineApi.ts` | `dr-screens-ops` | `dr-screens-public` | EventCheckInStationPage.tsx |
| `frontend/src/features/staff/eventCheckInOfflineStore.ts` | `dr-screens-ops` | `dr-screens-public` | EventCheckInStationPage.tsx |
| `frontend/src/features/staff/evidenceUi.ts` | `dr-screens-desk` | `dr-screens-public` | KioskReplayDetail.tsx |
| `frontend/src/features/staff/machinesApi.ts` | `dr-screens-ops` | `dr-screens-inventory` | ProcurementMoveModal.tsx |
| `frontend/src/features/staff/notificationDestinationTypes.ts` | `dr-screens-admin` | `dr-screens-ops` | ReportScheduleForm.tsx, reportSchedulesApi.ts |
| `frontend/src/features/staff/organizationsApi.ts` | `dr-screens-admin` | `dr-screens-ops` | EventOrganizers.tsx |
| `frontend/src/features/staff/panels/EvidenceUpload.tsx` | `dr-screens-desk` | `dr-screens-public` | KioskOnlineHandover.tsx, kioskApi.ts, kioskReplayApi.ts, kioskReplayClient.ts |
| `frontend/src/features/staff/panels/LoanTimeline.tsx` | `dr-screens-desk` | `dr-screens-inventory` | InventoryWorkspace.tsx |
| `frontend/src/features/staff/panels/QueuesInvalidation.ts` | `dr-screens-desk` | `dr-screens-public` | useKioskReplays.ts |
| `frontend/src/features/staff/panels/memberCards/ScanCardBox.tsx` | `dr-screens-ops` | `dr-screens-desk` | HandoverWizard.tsx |
| `frontend/src/features/staff/panels/memberCards/api.ts` | `dr-screens-ops` | `dr-screens-desk` | DirectHandoverWizard.tsx |
| `frontend/src/features/staff/panels/memberCards/types.ts` | `dr-screens-ops` | `dr-screens-public` | api.ts |
| `frontend/src/features/staff/panels/operationsReportsConfig.ts` | `dr-screens-ops` | `dr-screens-admin` | OrganizationAnalyticsPanel.tsx, organizationAnalyticsApi.ts |
| `frontend/src/features/staff/paymentsApi.ts` | `dr-screens-desk` | `dr-screens-admin` | MemberTermsDialog.tsx, MembershipPlanPicker.tsx, MembershipPlansSection.tsx |
| `frontend/src/features/staff/paymentsApi.ts` | `dr-screens-desk` | `dr-screens-ops` | OperationsReports.tsx |

(45 consumption edges; informational, not counted in the total.)

## 5. Untouched

No wave-3 screen imports these (dead code or unreachable from any route/tab). Leave them alone; deletion is out of scope for the revamp.

### Untouched — source (8 files)

| path | lines | evidence |
|---|---|---|
| `frontend/src/features/inventory/RequestSummary.tsx` | 40 | no importer |
| `frontend/src/features/staff/BookableSpaceMachineType.tsx` | 19 | no importer |
| `frontend/src/features/staff/HandoverDialogs.tsx` | 3 | no importer |
| `frontend/src/features/staff/handover/AssignBoxDialog.tsx` | 53 | only imported by HandoverDialogs.tsx |
| `frontend/src/features/staff/handover/IssueDialog.tsx` | 110 | only imported by HandoverDialogs.tsx |
| `frontend/src/features/staff/handover/ReturnDialog.tsx` | 149 | only imported by HandoverDialogs.tsx |
| `frontend/src/features/staff/handover/shared.tsx` | 88 | only imported by AssignBoxDialog.tsx, IssueDialog.tsx, ReturnDialog.tsx |
| `frontend/src/features/staff/handover/types.ts` | 36 | only imported by AssignBoxDialog.tsx, IssueDialog.tsx, ReturnDialog.tsx, shared.tsx |

### Untouched — tests (1 files)

| path | lines | follows |
|---|---|---|
| `frontend/src/features/staff/BookableSpaceMachineType.test.tsx` | 26 | tests BookableSpaceMachineType.tsx |

## 6. Check

- Universe: 522 source + 200 gitignored unit tests + 7 e2e files = **729**.
- Rows across all counted tables (tables whose header starts `| path | lines |`): 67 + 41 + 160 + 182 + 224 + 31 + 15 + 9 = **729** (desk + inventory + admin + ops + public + FROZEN + coordinator + untouched).
- The *Needs wave-3 coordinator edit* and *Consumes unchanged* tables repeat paths on purpose and are not counted.
- `check.py` (stdlib) parses the counted tables of this file and compares them with a fresh walk of the filesystem:

```
$ python check.py <repo> docs/design-revamp/OWNERSHIP.md
rows=729 unique=729 filesystem=729 dupes=0 missing=0 extra=0
PASS
```

**Total files = sum of all sections, and no path appears twice.**
