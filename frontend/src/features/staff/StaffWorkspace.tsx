import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { Link, Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { StaffShell } from "./StaffShell";
import { Callout, PageHeader } from "../../components/ui";
import { StaffListContext } from "./StaffListContext";
import { SetupChecklist } from "./SetupChecklist";
import { StaffTabContent } from "./StaffTabContent";
import { PiiAccessBanner } from "./PiiAccessBanner";
import { StaffScreenHelp } from "../help/HelpLink";
import { StaffHelpContext } from "../help/staffHelpContext";
import { EmptyState } from "../../components/ui/EmptyState";
import { getStaffAccess, STAFF_TAB_KEYS, TAB_LABELS } from "./staffAccess";
import {
  filterTabsByEnabledModules,
  readStoredStaffTab,
  keptStaffSubPath,
  staffSubPathFromPath,
  staffTabPath,
  tabFromStaffPath,
} from "./staffTabs";
import type { StaffAuthUser } from "../../lib/api";
import type { Makerspace } from "./panels/shared";

export function StaffWorkspace({
  activeMakerspace,
  actions,
  isMachineOnly,
  canConfigureMachineTypes,
  guestOnly,
  isSuperadmin,
  makerspaces,
  onAuthRefresh,
  selected,
  setSelected,
  setTab,
  signOut,
  singleTenantLocked,
  lockedMakerspaceId,
  user,
  notice,
}: {
  activeMakerspace?: Makerspace;
  actions: readonly string[];
  isMachineOnly: boolean;
  canConfigureMachineTypes: boolean;
  guestOnly: boolean;
  isSuperadmin: boolean;
  makerspaces: Makerspace[];
  onAuthRefresh: () => void;
  selected: number | null;
  setSelected: (id: number | null) => void;
  setTab: (tab: string) => void;
  signOut: () => Promise<void>;
  singleTenantLocked: boolean;
  lockedMakerspaceId?: number;
  user: StaffAuthUser;
  /** A console-wide notice above the page, e.g. the staff two-step grace banner (#128 C-1). */
  notice?: ReactNode;
}) {
  const location = useLocation();
  const {
    allowedTabs,
    canChooseToBuyKind,
    canEditInventory,
    canIssueDirectLoan,
    canCollectServiceRequests,
    canManageMakerspace,
    canUseMemberCards,
    canManageEvents,
    canManageBookings,
    canManageMachines,
    canManageQr,
    canSeeHardware,
    canSeePrinting,
    canUseToBuy,
    canViewAudit,
    defaultTab,
    grantOnly,
    handoutOnly,
    printingOnly,
  } = getStaffAccess(actions, isSuperadmin, singleTenantLocked, isMachineOnly, Boolean(user.event_grants?.length), Boolean(user.booking_grants?.length));
  const visibleMakerspaces =
    singleTenantLocked && activeMakerspace
      ? [activeMakerspace]
      : makerspaces;
  const moduleAllowedTabs = filterTabsByEnabledModules(allowedTabs, activeMakerspace);
  const routeTab = tabFromStaffPath(location.pathname, guestOnly);
  const routeTabDenied =
    !!routeTab && STAFF_TAB_KEYS.includes(routeTab) && !moduleAllowedTabs.includes(routeTab);
  const requestedTab = routeTab || readStoredStaffTab();
  const activeTab = moduleAllowedTabs.includes(requestedTab)
    ? requestedTab
    : moduleAllowedTabs.includes(defaultTab)
      ? defaultTab
      : moduleAllowedTabs[0] ?? defaultTab;
  // Without this the redirect below strips `/admin/machines/12-laser` back to
  // `/admin/machines` on every load, because the two strings differ -- so a per-type deep
  // link could never survive its first render. The rule lives in `keptStaffSubPath` so it
  // is testable on its own; rendering this whole workspace to assert one path string is
  // how that regression stays uncaught.
  const keptSubPath = keptStaffSubPath(
    routeTab,
    activeTab,
    staffSubPathFromPath(location.pathname, guestOnly),
  );
  const activeTabPath = activeTab
    ? staffTabPath(activeTab, guestOnly, isSuperadmin ? undefined : activeMakerspace?.slug, singleTenantLocked, keptSubPath)
    : staffTabPath(defaultTab, guestOnly, isSuperadmin ? undefined : activeMakerspace?.slug, singleTenantLocked);
  // Super Admin is GLOBAL authority and must win over any local membership row: a superuser who
  // also holds a membership would otherwise be announced as "Member". The deleted sidebar
  // prioritised it the same way.
  const activeMembership = user.makerspaces.find((item) => item.id === selected);
  const activeRoleName = isSuperadmin
    ? "Super Admin"
    : activeMembership?.role_names?.join(" + ") || activeMembership?.role_name;

  // A stale hardware bookmark for a machine-only actor returns to their allowed tab.
  const normalizedDeniedTabs = new Set(["requests"]);
  const normalizeDenied = routeTabDenied && !!routeTab && (
    normalizedDeniedTabs.has(routeTab) || (isSuperadmin && routeTab === "dashboard")
  );
  if ((!routeTabDenied || normalizeDenied) && location.pathname !== activeTabPath) {
    return <Navigate replace to={activeTabPath + location.search} />;
  }

  return (
    <StaffListContext.Provider value={{ ownerName: user.username, canShare: canManageMakerspace, actions, isSuperadmin }}>
    <StaffHelpContext.Provider value={{ makerspace: activeMakerspace, singleTenant: singleTenantLocked, platform: isSuperadmin }}>
      <StaffShell activeMakerspace={activeMakerspace} allowedTabs={moduleAllowedTabs} activeTab={routeTabDenied ? "" : activeTab}
        guestOnly={guestOnly} singleTenantLocked={singleTenantLocked} handoutOnly={handoutOnly} grantOnly={grantOnly} user={user}
        roleName={activeRoleName} isSuperadmin={isSuperadmin} makerspaces={makerspaces} setSelected={setSelected}
        setTab={setTab} signOut={signOut} actions={actions}>
        {notice}
        {/* #115: say plainly whose space this is; Lane C's PII banner is the action that opens or
            closes the window (the Users tab already renders it, so it is not shown twice there). */}
        {isSuperadmin && activeMakerspace && actions.length > 0 ? <div className="mb-4 grid gap-3"><Callout size="inline" tone="warn"
          lead={`Working in ${activeMakerspace.name} as the platform superadmin.`}
          body={t`Every change is audited in this space.`} />
          {activeTab !== "users" ? <PiiAccessBanner key={`pii:${activeMakerspace.id}`} makerspaceId={activeMakerspace.id} compact /> : null}</div> : null}
        {routeTabDenied ? <PageHeader title={t`Page unavailable`} /> : null}
        {routeTabDenied ? null : <StaffScreenHelp tab={activeTab} makerspace={activeMakerspace} singleTenant={singleTenantLocked} platform={isSuperadmin} />}
          {routeTabDenied ? (
            <EmptyState
              title={t`Access denied`}
              description={t`You don't have permission to view this page, or it isn't enabled for this makerspace.`}
              action={
                <Link className="desk-button-primary" to={consoleSessionHref(activeTabPath)}>
                  {t`Go to `}{TAB_LABELS[activeTab] ?? t`your workspace`}
                </Link>
              }
            />
          ) : (
            <StaffTabContent
              activeMakerspace={activeMakerspace}
              activeTab={activeTab}
              progress={activeMakerspace && canManageMakerspace && activeTab === "dashboard" ? <SetupChecklist key={`${user.username}:${activeMakerspace.id}`} makerspace={activeMakerspace} owner={user.username} allowedTabs={moduleAllowedTabs} guestOnly={guestOnly} singleTenantLocked={singleTenantLocked} /> : undefined}
              guestOnly={guestOnly || handoutOnly}
              makerspaces={visibleMakerspaces}
              isSuperadmin={isSuperadmin}
              currentUser={user}
              onAuthRefresh={onAuthRefresh}
              printingOnly={printingOnly}
              canChooseToBuyKind={canChooseToBuyKind}
              canEditInventory={canEditInventory}
              canIssueDirectLoan={canIssueDirectLoan}
              canCollectServiceRequests={canCollectServiceRequests}
              canUseToBuy={canUseToBuy}
              canManageQr={canManageQr}
              canManageMakerspace={canManageMakerspace}
              canUseMemberCards={canUseMemberCards}
              canManageEvents={canManageEvents}
              canManageBookings={canManageBookings}
              canManageMachines={canManageMachines}
              isMachineOnly={isMachineOnly}
              canConfigureMachineTypes={canConfigureMachineTypes}
              canSeeHardware={canSeeHardware}
              canSeePrinting={canSeePrinting}
              canViewAudit={canViewAudit}
              singleTenantLocked={singleTenantLocked}
              lockedMakerspaceId={lockedMakerspaceId}
            />
          )}
      </StaffShell>
    </StaffHelpContext.Provider>
    </StaffListContext.Provider>
  );
}
