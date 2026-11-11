import { t } from "@lingui/core/macro";
import { ModuleAnalytics } from "./panels/ModuleAnalytics";
import { capabilityOn } from "../../lib/features";
import { MyNotificationSettings } from "../notifications/MyNotificationSettings";
import { Suspense, type ReactNode } from "react";

import { ListLayout } from "../../components/layouts";
import { Skeleton } from "../../components/ui";
import type { StaffAuthUser } from "../../lib/api";
import { featureEnabled } from "../../lib/features";
import { getStaffAccess, REFUND_SUBJECT_ACTIONS } from "./staffAccess";
import { ownsAreaCharges } from "./paymentAccess";
import { filterTabsByEnabledModules } from "./staffTabs";
import { AreaAllowances } from "./allowances/AreaAllowances";
import { PlatformSpaceBreadcrumb } from "./platformConsole/PlatformSpaceBreadcrumb";
import { StaffPlatformTabContent } from "./StaffPlatformTabContent";
import type { Makerspace } from "./panels/shared";
import { StaffPanelErrorBoundary } from "./StaffPanelErrorBoundary";
import { PlatformProgrammeDashboard } from "./eventProgramme/PlatformProgrammeDashboard";
import { PLATFORM_CONSOLE_PAGES, PlatformConsoleContent } from "./platformConsole/platformConsolePages";
import { GrantedResourcesPanel } from "./GrantedResourcesPanel";
import { ConsumablesPanel, IncidentRegister, RepairsPanel, SchedulePanel } from "./StaffTabLoaders";
import { AllowedTabsContext } from "./areaOverview/allowedTabsContext";
import { ConsoleMemberActivity } from "./memberActivity/ConsoleMemberActivity";
import { ShopPanel, PlatformSpacesPanel, DonationsArea } from "./StaffTabLoaders";

import { PaymentsPanel, RefundQueue, FinancePanel, EventPayoutsSection, DevicesPanel, DashboardPanel, NotificationInbox, DirectLoans, Inventory, Ledger, MachinesPanel, EventsPanel, OrganizedEventsPanel, OrganizationAnalyticsPanel, OrganizationsPanel, BookingsPanel, MembersPanel, MemberCardsPanel, QrTools, RequestsPanel, OperationsReports, AuditLog, BulkImport, ScannerPanel, ContainersPanel, StocktakePanel, StockTransferPanel, ProcurementPanel, WarrantyPanel, AccountabilityPanel, Categories, NeedsFixTab, HandoverConsole } from "./StaffTabLoaders";

export function StaffTabContent({
  activeMakerspace,
  activeTab,
  progress,
  guestOnly,
  makerspaces,
  isSuperadmin,
  currentUser,
  onAuthRefresh,
  printingOnly,
  canChooseToBuyKind,
  canEditInventory,
  canIssueDirectLoan,
  canCollectServiceRequests,
  canUseToBuy,
  canManageQr,
  canManageMakerspace,
  canUseMemberCards,
  canManageMachines,
  isMachineOnly,
  canConfigureMachineTypes,
  canManageEvents,
  canManageBookings,
  canSeeHardware,
  canSeePrinting,
  canViewAudit,
  singleTenantLocked = false,
  lockedMakerspaceId,
}: {
  activeMakerspace?: Makerspace;
  activeTab: string;
  progress?: ReactNode;
  guestOnly: boolean;
  makerspaces: Makerspace[];
  isSuperadmin: boolean;
  currentUser: StaffAuthUser;
  onAuthRefresh: () => void;
  printingOnly: boolean;
  canChooseToBuyKind: boolean;
  canEditInventory: boolean;
  canIssueDirectLoan: boolean;
  canCollectServiceRequests: boolean;
  canUseToBuy: boolean;
  canManageQr: boolean;
  canManageMakerspace: boolean;
  canUseMemberCards: boolean;
  canManageMachines: boolean;
  isMachineOnly: boolean;
  canConfigureMachineTypes: boolean;
  canManageEvents: boolean;
  canManageBookings: boolean;
  canSeeHardware: boolean;
  canSeePrinting: boolean;
  canViewAudit: boolean;
  // Machines needs this for links; targetless organization panels need it as a mount gate.
  singleTenantLocked?: boolean;
  lockedMakerspaceId?: number;
}) {
  if (activeTab === "platform-dashboard" && isSuperadmin && !singleTenantLocked) {
    return <StaffPanelErrorBoundary resetKey="platform-dashboard"><Suspense fallback={<Skeleton className="h-40 w-full" />}><PlatformProgrammeDashboard /></Suspense></StaffPanelErrorBoundary>;
  }
  if (activeTab === "platform-spaces" && isSuperadmin && !singleTenantLocked) {
    return <StaffPanelErrorBoundary resetKey="platform-spaces"><Suspense fallback={<Skeleton className="h-40 w-full" />}><PlatformSpacesPanel /></Suspense></StaffPanelErrorBoundary>;
  }
  // The other platform pages (People & access, Security, Data & recovery, Settings, Analytics) need no chosen space.
  if (PLATFORM_CONSOLE_PAGES.includes(activeTab) && isSuperadmin && !singleTenantLocked) {
    return <StaffPanelErrorBoundary resetKey={activeTab}><Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <PlatformConsoleContent activeTab={activeTab} activeMakerspace={activeMakerspace} makerspaces={makerspaces} currentUser={currentUser} onAuthRefresh={onAuthRefresh} />
    </Suspense></StaffPanelErrorBoundary>;
  }
  if (activeTab === "organizations") {
    return <StaffPanelErrorBoundary resetKey="organizations"><Suspense fallback={<Skeleton className="h-40 w-full" />}><OrganizationsPanel isSuperadmin={isSuperadmin} makerspaces={makerspaces} /></Suspense></StaffPanelErrorBoundary>;
  }
  if (activeTab === "granted" && (currentUser.event_grants?.length || currentUser.booking_grants?.length)) {
    if (singleTenantLocked && lockedMakerspaceId === undefined) return <ListLayout header={{ title: t`Assigned resources` }} state={{ status: "ready" }}
      isEmpty empty={{ message: t`Unable to resolve this makerspace.` }} body={{ kind: "rows", rows: null }} />;
    return <StaffPanelErrorBoundary resetKey="granted"><Suspense fallback={<Skeleton className="h-40 w-full" />}><GrantedResourcesPanel eventGrants={currentUser.event_grants} bookingGrants={Boolean(currentUser.booking_grants?.length)} bookingGrantList={currentUser.booking_grants} makerspaceId={singleTenantLocked ? lockedMakerspaceId : undefined} /></Suspense></StaffPanelErrorBoundary>;
  }
  // Cross-venue organizer pages read no space: an organization member without a space role opens them too.
  if (!activeMakerspace && activeTab === "organized" && !isSuperadmin) {
    return <StaffPanelErrorBoundary resetKey="organized"><Suspense fallback={<Skeleton className="h-40 w-full" />}><OrganizedEventsPanel /></Suspense></StaffPanelErrorBoundary>;
  }
  if (!activeMakerspace && activeTab === "organization-analytics" && !isSuperadmin && !singleTenantLocked) {
    return <StaffPanelErrorBoundary resetKey="organization-analytics"><Suspense fallback={<Skeleton className="h-40 w-full" />}><OrganizationAnalyticsPanel makerspaces={makerspaces} /></Suspense></StaffPanelErrorBoundary>;
  }
  if (!activeMakerspace) {
    return <ListLayout header={{ title: t`No makerspace` }} state={{ status: "ready" }}
      isEmpty empty={{ message: t`Assign a makerspace to this account.` }} body={{ kind: "rows", rows: null }} />;
  }
  const makerspaceKey = activeMakerspace.id;
  // A platform superadmin has no membership row; inside a chosen space they hold every action (#115).
  const actorActions = isSuperadmin ? currentUser.superadmin_actions ?? []
    : currentUser.makerspaces.find((space) => space.id === makerspaceKey)?.actions ?? [];
  const allowedTabs = filterTabsByEnabledModules(getStaffAccess(actorActions, isSuperadmin, singleTenantLocked, isMachineOnly, false, false, currentUser.has_organizations !== false).allowedTabs, activeMakerspace, isSuperadmin ? undefined : actorActions);
  const has = (action: string) => isSuperadmin || actorActions.includes(action);
  return (
    <StaffPanelErrorBoundary resetKey={`${makerspaceKey}:${activeTab}`}>
      <AllowedTabsContext.Provider value={allowedTabs}><Suspense fallback={<div className="p-4"><Skeleton className="h-40 w-full" /></div>}>
      {/* #234 addendum 3(a): what is left of the limits this person manages; nothing when unlimited. */}
      {isSuperadmin && !singleTenantLocked ? <PlatformSpaceBreadcrumb spaceName={activeMakerspace.name} tab={activeTab} /> : null}
      <AreaAllowances key={`allowances:${makerspaceKey}`} makerspaceId={makerspaceKey} tab={activeTab} />
      <ConsoleMemberActivity key={`member-360:${makerspaceKey}`} makerspaceId={makerspaceKey} activeTab={activeTab} actions={actorActions} isSuperadmin={isSuperadmin} />
      {activeTab === "devices" && (isSuperadmin || currentUser.makerspaces.some(
        (space) => space.id === makerspaceKey && space.actions.includes("manage_devices"),
      )) && activeMakerspace.enabled_modules?.includes("devices") ? (
        <DevicesPanel key={makerspaceKey} makerspaceId={makerspaceKey} />
      ) : null}
      {activeTab === "dashboard" ? (
        <DashboardPanel key={makerspaceKey} makerspace={activeMakerspace} canManageMakerspace={canManageMakerspace} allowedTabs={allowedTabs} actions={actorActions} isSuperadmin={isSuperadmin} progress={progress} singleTenantLocked={singleTenantLocked} guestOnly={guestOnly} />
      ) : null}
      {activeTab === "notifications" ? (
        <NotificationInbox key={makerspaceKey} makerspace={activeMakerspace} canManageMembers={has("manage_members")} />
      ) : null}
      {activeTab === "channels" && !isSuperadmin && actorActions.length > 0 ? <section className="desk-panel p-5">
        <h1 className="title-panel mb-4">{t`My notification channels`}</h1>
        <MyNotificationSettings key={makerspaceKey} makerspaceId={makerspaceKey} />
      </section> : null}
      {activeTab === "requests" ? (
        <RequestsPanel
          key={makerspaceKey}
          makerspace={activeMakerspace}
          guestOnly={guestOnly}
          canSeeHardware={canSeeHardware}
          canViewAudit={canViewAudit}
        />
      ) : null}
      {activeTab === "inventory" ? (
        <Inventory
          key={makerspaceKey}
          makerspace={activeMakerspace}
          canViewAudit={canViewAudit}
          canUseToBuy={canUseToBuy}
          canEditInventory={canEditInventory}
        />
      ) : null}
      {activeTab === "needsfix" && canEditInventory ? <NeedsFixTab key={makerspaceKey} makerspace={activeMakerspace} /> : null}
      {activeTab === "categories" && canEditInventory ? <Categories key={makerspaceKey} makerspace={activeMakerspace} /> : null}      {activeTab === "machines" ? (
        <MachinesPanel
          key={makerspaceKey}
          makerspaceId={activeMakerspace.id}
          canManage={canManageMachines}
          publicSiteEnabled={activeMakerspace.public_site_enabled ?? false}
          enabledFeatures={activeMakerspace.enabled_features ?? []}
          canConfigureMachineTypes={canConfigureMachineTypes}
          maintenanceEnabled={capabilityOn(activeMakerspace, "machines.maintenance")}
          machineServiceEnabled={activeMakerspace.enabled_modules?.includes("machine_service") ?? false}
          printingEnabled={activeMakerspace.enabled_modules?.includes("printing") ?? false}
          reportsEnabled={activeMakerspace.enabled_modules?.includes("reports") ?? false}
          guestOnly={guestOnly}
          makerspaceSlug={activeMakerspace.slug}
          singleTenantLocked={singleTenantLocked}
          printerAdapter={has("manage_devices") && ["devices", "machine_service"].every((key) => activeMakerspace.enabled_modules?.includes(key))}
          delegatedRecipientRulesEnabled={
            isMachineOnly &&
            (activeMakerspace.enabled_modules ?? []).includes("notifications") &&
            featureEnabled(
              activeMakerspace.enabled_features ?? [],
              "notifications.delegated_recipients",
            )
          }
        />
      ) : null}
      {activeTab === "events" && canManageEvents ? <EventsPanel key={makerspaceKey} enabledFeatures={activeMakerspace.enabled_features} enabledModules={activeMakerspace.enabled_modules} publicSiteEnabled={activeMakerspace.public_site_enabled ?? false} makerspaceId={activeMakerspace.id} /> : null}
      {activeTab === "organized" && !isSuperadmin ? <OrganizedEventsPanel /> : null}
      {activeTab === "organization-analytics" && !isSuperadmin && !singleTenantLocked ? (
        <OrganizationAnalyticsPanel makerspaces={makerspaces} />
      ) : null}
      {activeTab === "bookings" && canManageBookings ? <BookingsPanel key={makerspaceKey} makerspaceId={activeMakerspace.id} recurringEnabled={activeMakerspace.enabled_features?.includes("bookings.recurring")} publicSiteEnabled={activeMakerspace.public_site_enabled ?? false} /> : null}
      {activeTab === "members" && has("manage_members") ? (
        <MembersPanel
          key={makerspaceKey}
          makerspaceId={activeMakerspace.id}
          actorActions={actorActions}
          isSuperadmin={isSuperadmin}
          onAuthRefresh={onAuthRefresh}
          membershipEnabled={(activeMakerspace.enabled_modules ?? []).includes("membership")}
          presenceEnabled={(activeMakerspace.enabled_modules ?? []).includes("presence")}
          canManageMakerspace={canManageMakerspace}
          canViewFinance={has("view_finance")}
          canRecordPayment={has("record_payment")}
          enabledFeatures={activeMakerspace.enabled_features ?? []}
          makerspaceSlug={activeMakerspace.slug}
        />
      ) : null}
      {activeTab === "cards" && canUseMemberCards ? (
        <MemberCardsPanel key={makerspaceKey} makerspaceId={activeMakerspace.id} enabledFeatures={activeMakerspace.enabled_features ?? []} />
      ) : null}
      {activeTab === "payments" && (has("view_finance") || has("record_payment") || ownsAreaCharges(actorActions)) ? <PaymentsPanel key={makerspaceKey} makerspaceId={activeMakerspace.id} makerspaceName={activeMakerspace.name} actorActions={actorActions} isSuperadmin={isSuperadmin} /> : null}
      {activeTab === "refunds" && allowedTabs.includes("refunds") ? <RefundQueue key={makerspaceKey} makerspaceId={activeMakerspace.id}
        makerspaceName={activeMakerspace.name} canEditPolicy={canManageMakerspace} enabledFeatures={activeMakerspace.enabled_features ?? []}
        canDecide={["manage_events", "manage_bookings", "manage_machines", "manage_members", "manage_makerspace", ...REFUND_SUBJECT_ACTIONS].some(has)} /> : null}
      {activeTab === "finance" && allowedTabs.includes("finance") ? <FinancePanel key={makerspaceKey} makerspace={activeMakerspace}
        canViewFinance={has("view_finance")} canRecordPayment={has("record_payment")} /> : null}
      {activeTab === "payments" && has("view_finance") ? <EventPayoutsSection key={`payouts:${makerspaceKey}`} makerspaceId={activeMakerspace.id} /> : null}
      {activeTab === "tobuy" ? (
        <ProcurementPanel
          key={makerspaceKey}
          makerspace={activeMakerspace}
          canChooseKind={canChooseToBuyKind}
          inventoryTabAvailable={allowedTabs.includes("inventory")}
        />
      ) : null}
      {activeTab === "consumables" && allowedTabs.includes("consumables") ? <ConsumablesPanel key={makerspaceKey} makerspace={activeMakerspace} canEditInventory={canEditInventory} /> : null}
      {activeTab === "repairs" && allowedTabs.includes("repairs") ? <RepairsPanel key={makerspaceKey} makerspace={activeMakerspace}
        actions={isSuperadmin ? [...actorActions, "manage_makerspace", "manage_machines", "edit_inventory", "manage_bookings"] : actorActions} /> : null}
      {activeTab === "incidents" && allowedTabs.includes("incidents") ? <IncidentRegister key={makerspaceKey} makerspace={activeMakerspace} /> : null}
      {activeTab === "schedule" && allowedTabs.includes("schedule") ? <SchedulePanel key={makerspaceKey} makerspace={activeMakerspace} allowedTabs={allowedTabs}
        guestOnly={guestOnly} singleTenantLocked={singleTenantLocked} groupByArea={canManageMakerspace} /> : null}
      {activeTab === "shop" && allowedTabs.includes("shop") ? <ShopPanel key={makerspaceKey} makerspace={activeMakerspace} actions={actorActions} isSuperadmin={isSuperadmin} /> : null}
      {activeTab === "donations" && allowedTabs.includes("donations") ? <DonationsArea key={makerspaceKey} makerspace={activeMakerspace} actions={actorActions} isSuperadmin={isSuperadmin} /> : null}
      {activeTab === "transfers" && (canEditInventory || isSuperadmin) ? (
        <StockTransferPanel
          key={makerspaceKey}
          makerspace={activeMakerspace}
          makerspaces={makerspaces}
          isSuperadmin={isSuperadmin}
          canEditInventory={canEditInventory}
        />
      ) : null}
      {activeTab === "stocktake" && canEditInventory ? <StocktakePanel key={makerspaceKey} makerspace={activeMakerspace} isSuperadmin={isSuperadmin} canConfigure={canManageMakerspace} /> : null}
      {activeTab === "containers" && canManageQr ? <ContainersPanel key={makerspaceKey} makerspace={activeMakerspace} canEditInventory={canEditInventory} /> : null}
      {activeTab === "ledger" ? (
        <Ledger
          key={makerspaceKey}
          makerspace={activeMakerspace}
          isSuperadmin={isSuperadmin}
          canExport={!getStaffAccess(actorActions, isSuperadmin, singleTenantLocked).handoutOnly}
        />
      ) : null}
      {activeTab === "warranty" && (canEditInventory || canSeePrinting) ? (
        <WarrantyPanel
          key={makerspaceKey}
          makerspace={activeMakerspace}
          canEditInventory={canEditInventory}
        />
      ) : null}
      {activeTab === "accountability" && allowedTabs.includes("accountability") ? (
        <AccountabilityPanel key={makerspaceKey} makerspace={activeMakerspace} isSuperadmin={isSuperadmin} inventoryView={!has("manage_members")} />
      ) : null}
      {activeTab === "reports" ? (
        <OperationsReports
          key={makerspaceKey}
          makerspace={activeMakerspace}
          makerspaces={makerspaces}
          isSuperadmin={isSuperadmin}
          printingOnly={printingOnly}
          canViewAudit={canViewAudit}
          canManageMachines={canManageMachines}
          canViewFinance={has("view_finance")}
        />
      ) : null}
      {activeTab === "direct" && canIssueDirectLoan ? <DirectLoans key={makerspaceKey} makerspace={activeMakerspace} /> : null}
      {activeTab === "handover" && canCollectServiceRequests ? (
        <HandoverConsole key={makerspaceKey} makerspaceId={makerspaceKey} enabled />
      ) : null}
      {activeTab === "bulk" && canEditInventory ? <BulkImport key={makerspaceKey} makerspace={activeMakerspace} /> : null}
      {activeTab === "qr" && canManageQr ? <QrTools key={makerspaceKey} makerspace={activeMakerspace} /> : null}
      {activeTab === "scanner" && canManageQr ? (
        <ScannerPanel
          key={makerspaceKey}
          makerspace={activeMakerspace}
          isSuperadmin={isSuperadmin}
          makerspaces={makerspaces}
        />
      ) : null}
      <StaffPlatformTabContent activeTab={activeTab} activeMakerspace={activeMakerspace} makerspaces={makerspaces} isSuperadmin={isSuperadmin} canManageMakerspace={canManageMakerspace} currentUser={currentUser} onAuthRefresh={onAuthRefresh} allowedTabs={allowedTabs} singleTenantLocked={singleTenantLocked} />
      {activeTab === "audit" && allowedTabs.includes("audit") ? <AuditLog makerspaceId={activeMakerspace?.id} actions={isSuperadmin ? undefined : actorActions} /> : null}
      <ModuleAnalytics key={`analytics:${makerspaceKey}:${activeTab}`} makerspace={activeMakerspace} tab={activeTab} singleTenantLocked={singleTenantLocked} guestOnly={guestOnly} />
      </Suspense></AllowedTabsContext.Provider>
    </StaffPanelErrorBoundary>
  );
}
