import { AUDIT_AREA_ACTIONS, canReadAudit } from "./panels/auditAreas";
import { ownsAreaCharges, ownsLoanCharges } from "./paymentAccess";
const ALL_TABS = [
  "platform-dashboard", "platform-spaces", "platform-inbox", "platform-access", "platform-security", "platform-data", "platform-limits", "usage",
  "dashboard", "notifications", "channels", "requests", "direct", "handover", "inventory", "needsfix", "categories", "machines", "events", "organized", "granted", "bookings", "members", "cards", "tobuy", "transfers",
  "stocktake", "containers", "ledger", "reports", "accountability", "warranty", "bulk", "qr", "scanner", "api", "settings", "security", "emailtemplates", "users", "platform", "audit",
  "devices", "email-logs", "payments", "refunds", "finance", "organizations", "organization-analytics", "modules", "exports", "backups", "migration",
  "consumables", "repairs", "incidents",
  // Decision 242(k): the staff Schedule (bookings, events, shifts, machine jobs, maintenance).
  "schedule",
  "shop", "donations",
  // L25 (#163B): the space's Metabase dashboards, and the platform-wide Metabase.
  "analytics", "platform-analytics",
] as const;

export const STAFF_TAB_KEYS: readonly string[] = ALL_TABS;

// What a superadmin sees before choosing a space (surface_policy.PLATFORM_ROUTES). Once a
// space is chosen they also hold every action there (owner decision #115) and see exactly
// that space's Space-Manager tabs; `StaffApp` passes `superadmin_actions` only then.
// People & access, Security and Data & recovery (0.12.0) are platform pages that open
// without a chosen space, like the dashboard and Spaces (features/staff/platformConsole/).
const PLATFORM_TABS = ["platform-dashboard", "platform-spaces", "platform-inbox", "platform-access", "platform-security", "platform-data", "platform-limits", "users", "security", "organizations", "modules", "backups", "migration", "platform", "platform-analytics"];
/** Platform pages a multi-space deployment shows; a single-tenant console has none of them. */
const PLATFORM_ONLY_TABS = ["platform-dashboard", "platform-spaces", "platform-inbox", "platform-access", "platform-security", "platform-data", "platform-limits", "platform", "platform-analytics"];

export { TAB_LABELS } from "./staffTabLabels";

// Permissions only. Module availability is decided in exactly one place --
// `filterTabsByEnabledModules` in staffTabs.ts -- because two maps naming the same tab
// is how a tab ends up gated in the sidebar but not on the route, or vice versa.
/**
 * `isMachineOnly` is SERVER-derived (`is_machine_only` on the membership) and must not be
 * re-derived from `actions`: a null-`assigned_role` legacy membership is scope-exempt and
 * cannot be expressed here, and holding `manage_machines` is a different question from
 * being narrowed by machine scope. The backend refuses the notification inbox for exactly
 * this actor, so a locally-guessed value would render a tab that 403s on every request.
 *
 * `hasOrganizations` is the auth payload's `has_organizations` (0.12.0 audit row 9): the
 * cross-venue Organizations group is shown only to a person in at least one organization.
 * It defaults to true so a payload without the flag keeps the old behaviour.
 */
export function getStaffAccess(
  actions: readonly string[],
  isSuperadmin: boolean,
  singleTenantLocked: boolean,
  _isMachineOnly = false,
  hasEventGrants = false,
  hasBookingGrants = false,
  hasOrganizations = true,
) {
  const hasGrants = hasEventGrants || hasBookingGrants;
  const has = (action: string) => actions.includes(action);
  const canEditInventory = has("edit_inventory");
  const canViewInventory = has("view_inventory");
  const canSeePrinting = has("manage_printing") || has("manage_machines");
  const canManageMachines = has("manage_machines");
  const canManageEvents = has("manage_events");
  const canManageBookings = has("manage_bookings");
  const canViewAudit = has("view_audit");
  // #219(e-1): area roles read the audit log narrowed to their area without view_audit.
  const canReadAuditLog = canReadAudit(actions);
  const canManageQr = has("manage_qr");
  const canManageMakerspace = isSuperadmin || has("manage_makerspace");
  const canManageMembers = has("manage_members");
  const canViewFinance = has("view_finance");
  const canRecordPayment = has("record_payment");
  // Mirrors the backend gate: the member-card endpoints check SCAN_MEMBER_CARDS /
  // MANAGE_MEMBER_CARDS, never MANAGE_MAKERSPACE. Space Manager holds the manage action by
  // default. Organization-derived grants may hold only the scan action, so keep
  // this gate action-based rather than assuming a local role's catalogue grants.
  const canUseMemberCards = canManageMembers || has("manage_member_cards") || has("scan_member_cards");
  // Parity O-B1: the unit tree. Managing implies viewing (rbac IMPLIED_ACTIONS); both live inside the
  // Members tab and Settings, so neither opens a tab of its own.
  const canManageMemberUnits = isSuperadmin || has("manage_member_units");
  const canViewMemberUnits = canManageMemberUnits || has("view_member_units");
  const canIssueDirectLoan = has("issue_direct_loan");
  const canSeeHardware = ["accept_request", "reject_request", "assign_box", "issue_request", "issue_direct_loan", "return_request"].some((action) => actions.includes(action));
  const canUseToBuy = has("edit_inventory") || has("manage_printing") || has("manage_machines") || has("manage_makerspace");
  const canChooseToBuyKind = has("manage_makerspace");
  const canSeeDashboard = has("view_inventory") || has("manage_printing") || has("manage_machines")
    || has("manage_makerspace") || has("manage_events") || has("manage_bookings")
    || has("manage_members") || canViewFinance
    // Decision 242(i): the server now serves the Shop Manager and the Technician their area's tiles.
    || has("manage_shop") || has("work_repairs");
  const governanceOnly = !isSuperadmin && actions.length === 0 && !singleTenantLocked;
  // Mirrors rbac.HANDOUT_ACTIONS / _HANDOUT_MUTATIONS. `collect_service_request` belongs
  // here so a front-desk role that also hands over finished machine jobs still reads as
  // handover-only and keeps the narrow tab set, rather than being shown the whole console.
  const HANDOUT = ["view_inventory", "assign_box", "issue_request", "issue_direct_loan", "return_request", "upload_evidence", "collect_service_request", "record_payment"];
  const HANDOUT_MUTATIONS = ["assign_box", "issue_request", "issue_direct_loan", "return_request", "upload_evidence", "collect_service_request", "record_payment"];
  const handoutOnly = !isSuperadmin && actions.length > 0 && actions.every((action) => HANDOUT.includes(action)) && actions.some((action) => HANDOUT_MUTATIONS.includes(action));
  // Mirrors the backend IMPLIED_ACTIONS edge: managing machines includes handing their
  // finished work over, so a manager needs no separate grant.
  const canCollectServiceRequests = has("collect_service_request") || canManageMachines;
  const printingOnly = canSeePrinting && !canEditInventory && !canManageMakerspace;
  // Audit IN11 (decision 248): the desk reads the Ledger ("who has what") read-only; no exports (224(d)).
  const baseTabs = handoutOnly ? (["dashboard", "requests", "direct", "handover", "payments", "notifications", "channels", "ledger", "granted"] as const) : ALL_TABS;
  const grantOnly = !isSuperadmin && actions.length === 0 && hasGrants;
  // Central organization governance is independent of makerspace actions. An
  // event grant adds a workspace without replacing that existing global surface.
  // Role-screen audit 0.12.0: the organizer list and organization analytics are served to
  // any active person (OrganizedEventListView is IsActiveStaff), so an organization member
  // with no space role reaches them too instead of a console with only Organizations.
  const organizationTabs = hasOrganizations ? ORGANIZATION_TABS : ["organizations"];
  const allowedTabs: readonly string[] = isSuperadmin && actions.length === 0
    ? PLATFORM_TABS.filter(tab => !singleTenantLocked || ![...PLATFORM_ONLY_TABS, "organizations"].includes(tab))
    : grantOnly ? (singleTenantLocked || !hasOrganizations ? ["granted"] : ["granted", ...ORGANIZATION_TABS]) : governanceOnly ? organizationTabs : baseTabs.filter((tabName) => {
    // The superadmin governs every organization (the payload flag is false for them).
    if (ORGANIZATION_TABS.includes(tabName) && !hasOrganizations && !isSuperadmin) return false;
    if (tabName === "granted") return hasGrants;
    if (PLATFORM_ONLY_TABS.includes(tabName)) return isSuperadmin && !singleTenantLocked;
    if (tabName === "usage") return canManageMakerspace;
    if (tabName === "dashboard") return handoutOnly || isSuperadmin || canSeeDashboard;
    // Personal rows and read state admit machine-only and handover staff.
    if (tabName === "notifications") return isSuperadmin || actions.length > 0;
    // Personal delivery channels belong to a staff account, not to the space.
    if (tabName === "channels") return !isSuperadmin && actions.length > 0;
    if (tabName === "tobuy") return canUseToBuy;
    // The merged list reads items (view_inventory) and machine/pool rows (machine scope).
    if (tabName === "consumables") return canViewInventory || canSeePrinting;
    if (tabName === "needsfix") return canEditInventory;
    if (tabName === "categories") return canEditInventory;
    if (tabName === "bulk") return canEditInventory;
    if (tabName === "stocktake") return canEditInventory;
    if (tabName === "direct") return canIssueDirectLoan;
    if (tabName === "handover") return canCollectServiceRequests;
    if (tabName === "inventory") return canViewInventory;
    if (tabName === "ledger") return canViewInventory;
    if (tabName === "transfers") return canEditInventory || isSuperadmin;
    if (tabName === "containers") return canManageQr;
    if (tabName === "qr") return canManageQr;
    if (tabName === "scanner") return canManageQr;
    if (tabName === "audit") return canReadAuditLog;
    // Decision 224(a): the accountability page is the people area's (MANAGE_MEMBERS; the Space
    // Manager holds it); view_audit alone no longer opens it.
    // Decision 248 / IN8: the Inventory Manager reads it too (overdue and repeat damage, read-only);
    // the handout desk stays counter-only (224(d)).
    if (tabName === "accountability") return canManageMembers || (canViewInventory && !handoutOnly);
    // Decision 217: every action some report definition requires (`required_action` or
    // `alternate_actions`); the server still filters the catalogue per definition.
    if (tabName === "reports") return canViewFinance || canViewAudit || canSeePrinting || canManageMachines || canManageEvents || canManageBookings
      || REPORT_ACTIONS.some(has);
    if (tabName === "warranty") return canEditInventory || canSeePrinting;
    if (tabName === "users") return canManageMakerspace;
    if (tabName === "settings") return canManageMakerspace;
    // The backend narrows further: only this space's Space Manager or a platform superadmin.
    if (tabName === "security") return canManageMakerspace;
    if (tabName === "emailtemplates") return canEditInventory || canSeePrinting || has("manage_devices") || canManageEvents || canManageBookings;
    if (tabName === "email-logs") return canManageMakerspace;
    // L25: view_analytics (the Space Manager holds it through manage_makerspace).
    if (tabName === "analytics") return isSuperadmin || has("view_analytics") || has("manage_makerspace");
    // #128 C-10: the Space Manager switches modules on and off (data kept); the server
    // keeps limit-gated installs on the managed platform for the superadmin.
    if (tabName === "modules") return canManageMakerspace;
    if (tabName === "devices") return has("manage_devices");
    // L16: the area managers (#102) and the Technician (#128 C-3); the server narrows every row.
    if (tabName === "repairs") return canEditInventory || canManageMachines || canManageBookings || canManageMakerspace
      || ["work_repairs", "run_maintenance", "set_service_state"].some(has);
    // #223(k): the Space Manager or any area reader (incidents/scope.py); the server narrows every row.
    if (tabName === "incidents") return canManageMakerspace || INCIDENT_READER_ACTIONS.some(has);
    if (tabName === "machines") return canManageMachines;
    // Decision 242(k): a layer exists for each of these (operations/schedule.available_layers); the server narrows rows.
    if (tabName === "schedule") return canManageMakerspace || canManageBookings || canManageEvents || canManageMachines
      || canEditInventory || ["work_repairs", "run_maintenance"].some(has);
    if (tabName === "events") return canManageEvents;
    // Organizer authority is per event and cross-venue; selected-space actions cannot
    // describe it. Superadmins are excluded because the organizer endpoint excludes them.
    // Excluded in a single-tenant deployment too: the organizer list is a TARGETLESS global
    // route, and origin_scope._global_endpoint_allowed permits only `admin-makerspaces` on a
    // hard-scoped staff origin, so on a verified custom domain the tab would render and then
    // 403 on every load. Those users reach it through the central console instead.
    if (tabName === "organized") return !isSuperadmin && !singleTenantLocked;
    // Like organized events, organization analytics is targetless and cross-makerspace.
    // A hard-scoped tenant origin rejects it before application authorization runs.
    if (tabName === "organization-analytics") return !isSuperadmin && !singleTenantLocked;
    if (tabName === "organizations") return !singleTenantLocked;
    if (tabName === "bookings") return canManageBookings;
    if (tabName === "members") return canManageMembers;
    if (tabName === "cards") return canUseMemberCards;
    // Decision 242(a): every charge owner gets their own-area queue (PaymentsPanel area mode);
    // finance staff keep the whole ledger. The handout desk stays narrow (217(b), decision 259): it opens
    // Payments for LOAN charges only (the deposit and late fees its issue/return actions own), or the
    // recording ledger with record_payment; never another area's money.
    if (tabName === "payments") return canViewFinance || canRecordPayment || (handoutOnly ? ownsLoanCharges(actions) : ownsAreaCharges(actions));
    // Mirrors `refund_case_access.may_read_queue`: finance reads every case, each domain's
    // staff read the cases for the charges they own. Cash-recording alone is not enough.
    // Decision 217: loan charges belong to whoever issues/takes returns and shop orders to
    // the Shop Manager (reconciliation_authority.SUBJECT_ACTIONS), so both read their cases.
    if (tabName === "refunds") return canViewFinance || canManageEvents || canManageBookings || canManageMachines
      || canManageMembers || canManageMakerspace || REFUND_SUBJECT_ACTIONS.some(has);
    // #100: each area's manager sees that area's money; the server narrows every list.
    // Decision 217: shop money is the Shop Manager's area (finance_scope.DOMAIN_ACTIONS).
    if (tabName === "finance") return canViewFinance || canRecordPayment || canEditInventory || canManageBookings
      || canManageMachines || canManageEvents || has("manage_shop");
    if (tabName === "exports") return canManageMakerspace;
    if (tabName === "backups") return canManageMakerspace;
    if (tabName === "migration") return isSuperadmin;
    // L22: the shop actions; the Space Manager holds them through manage_makerspace (rbac IMPLIED_ACTIONS).
    if (tabName === "shop") return has("view_shop") || has("sell_shop") || has("manage_shop") || canManageMakerspace;
    // Decision 242(m): donations are the Space Manager's (manage_makerspace implies manage_donations),
    // the Fundraising role's and finance staff's (payments/donations/gates.py); never an area manager's.
    if (tabName === "donations") return canViewFinance || has("manage_donations") || canManageMakerspace;
    if (tabName === "requests") return canSeeHardware;
    return true;
  });
  return {
    grantOnly,
    handoutOnly,
    printingOnly,
    canSeeHardware,
    canSeePrinting,
    canUseToBuy,
    canEditInventory,
    canViewInventory,
    canIssueDirectLoan,
    canViewAudit,
    canReadAuditLog,
    canManageQr,
    canManageMakerspace,
    canUseMemberCards,
    canManageMembers,
    canManageMemberUnits,
    canViewMemberUnits,
    canViewFinance,
    canRecordPayment,
    canManageMachines,
    canManageEvents,
    canManageBookings,
    canCollectServiceRequests,
    canChooseToBuyKind,
    allowedTabs,
    // The backend serves handover-only actors an operational queue home.
    defaultTab: staffLandingTab(allowedTabs) ?? "dashboard",
  };
}

/** The cross-venue Organizations group: hidden for a person with no organization (audit row 9). */
const ORGANIZATION_TABS = ["organizations", "organized", "organization-analytics"];

/** Actions admitting at least one report definition beyond the tab's named managers. */
const REPORT_ACTIONS = ["edit_inventory", "view_inventory", "manage_members", "scan_member_cards", "manage_shop",
  "work_repairs", "manage_makerspace", "manage_donations"];
/** Area actions that open the incident register (twin of incidents/scope.READER_AREAS). */
const INCIDENT_READER_ACTIONS = (["lending", "machines", "events", "bookings"] as const).flatMap(area => AUDIT_AREA_ACTIONS[area]);
/** Refund-case subject authorities not already covered by a named manager (SUBJECT_ACTIONS). */
export const REFUND_SUBJECT_ACTIONS = ["issue_request", "return_request", "manage_shop", "manage_donations"];

// Decision 217(d): the home is the dashboard when the server serves one (since 242(i) also for
// the Shop Manager and Technician); otherwise staff land on their own work, not the inbox.
const LANDING_PRIORITY = ["dashboard", "shop", "repairs", "donations"];

/** The landing tab for an already permission- or module-filtered tab list. */
export function staffLandingTab(tabs: readonly string[]): string | undefined {
  return LANDING_PRIORITY.find(tab => tabs.includes(tab)) ?? tabs[0];
}
