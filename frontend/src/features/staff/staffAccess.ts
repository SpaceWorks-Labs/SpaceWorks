const ALL_TABS = [
  "platform-dashboard", "usage",
  "dashboard", "notifications", "channels", "requests", "direct", "handover", "inventory", "needsfix", "categories", "machines", "events", "organized", "granted", "bookings", "members", "cards", "tobuy", "transfers",
  "stocktake", "containers", "ledger", "reports", "accountability", "warranty", "bulk", "qr", "scanner", "api", "settings", "security", "emailtemplates", "users", "platform", "audit",
  "devices", "email-logs", "payments", "refunds", "finance", "organizations", "organization-analytics", "modules", "exports", "backups", "migration",
] as const;

export const STAFF_TAB_KEYS: readonly string[] = ALL_TABS;

// What a superadmin sees before choosing a space (surface_policy.PLATFORM_ROUTES). Once a
// space is chosen they also hold every action there (owner decision #115) and see exactly
// that space's Space-Manager tabs; `StaffApp` passes `superadmin_actions` only then.
const PLATFORM_TABS = ["platform-dashboard", "users", "security", "organizations", "modules", "backups", "migration", "platform"];

export const TAB_LABELS: Record<string, string> = {
  "platform-dashboard": "Platform dashboard",
  usage: "Usage & limits",
  dashboard: "Dashboard",
  notifications: "Notifications",
  channels: "My channels",
  requests: "Requests",
  direct: "Direct handout",
  handover: "Job handover",
  ledger: "Ledger",
  inventory: "Inventory",
  categories: "Categories",
  needsfix: "To-be-fixed",
  stocktake: "Stocktake",
  transfers: "Transfers",
  containers: "Containers",
  bulk: "Bulk import",
  qr: "QR Tools",
  scanner: "Scanner",
  machines: "Machines",
  devices: "Devices",
  events: "Events",
  organized: "Organized events",
  granted: "Assigned resources",
  bookings: "Bookings",
  members: "Members",
  cards: "Member cards",
  tobuy: "To Buy",
  reports: "Reports",
  "organization-analytics": "Organization analytics",
  organizations: "Organizations",
  accountability: "Accountability",
  warranty: "Warranties",
  audit: "Audit log",
  users: "Users",
  settings: "Settings",
  security: "Security",
  emailtemplates: "Email templates",
  "email-logs": "Delivery logs",
  api: "API access",
  platform: "Platform settings",
  payments: "Payments",
  refunds: "Refunds",
  finance: "Finance",
  modules: "Modules",
  exports: "Data export",
  backups: "Backup & restore",
  migration: "Tenant migration",
};

export const TAB_GROUPS: { label: string; tabs: string[] }[] = [
  { label: "Operate", tabs: ["dashboard", "notifications", "channels", "requests", "direct", "handover", "payments", "refunds", "finance", "ledger", "transfers", "stocktake", "tobuy"] },
  { label: "Inventory", tabs: ["inventory", "categories", "needsfix", "containers", "bulk", "qr", "scanner"] },
  { label: "Machines", tabs: ["machines", "devices"] },
  { label: "Events", tabs: ["events", "organized", "granted"] },
  { label: "Bookings", tabs: ["bookings"] },
  { label: "Members", tabs: ["members", "cards"] },
  { label: "Insights", tabs: ["reports", "organization-analytics", "accountability", "warranty", "audit"] },
  { label: "Organizations", tabs: ["organizations"] },
  { label: "Admin", tabs: ["users", "settings", "security", "usage", "emailtemplates", "email-logs", "api", "exports", "backups", "migration", "modules", "platform-dashboard", "platform"] },
];

// Permissions only. Module availability is decided in exactly one place --
// `filterTabsByEnabledModules` in staffTabs.ts -- because two maps naming the same tab
// is how a tab ends up gated in the sidebar but not on the route, or vice versa.
/**
 * `isMachineOnly` is SERVER-derived (`is_machine_only` on the membership) and must not be
 * re-derived from `actions`: a null-`assigned_role` legacy membership is scope-exempt and
 * cannot be expressed here, and holding `manage_machines` is a different question from
 * being narrowed by machine scope. The backend refuses the notification inbox for exactly
 * this actor, so a locally-guessed value would render a tab that 403s on every request.
 */
export function getStaffAccess(
  actions: readonly string[],
  isSuperadmin: boolean,
  singleTenantLocked: boolean,
  _isMachineOnly = false,
  hasEventGrants = false,
  hasBookingGrants = false,
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
  const canIssueDirectLoan = has("issue_direct_loan");
  const canSeeHardware = ["accept_request", "reject_request", "assign_box", "issue_request", "issue_direct_loan", "return_request"].some((action) => actions.includes(action));
  const canUseToBuy = has("edit_inventory") || has("manage_printing") || has("manage_machines") || has("manage_makerspace");
  const canChooseToBuyKind = has("manage_makerspace");
  const canSeeDashboard = has("view_inventory") || has("manage_printing") || has("manage_machines")
    || has("manage_makerspace") || has("manage_events") || has("manage_bookings")
    || has("manage_members") || canViewFinance;
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
  const baseTabs = handoutOnly ? (["dashboard", "requests", "direct", "handover", "payments", "notifications", "channels", "granted"] as const) : ALL_TABS;
  const grantOnly = !isSuperadmin && actions.length === 0 && hasGrants;
  // Central organization governance is independent of makerspace actions. An
  // event grant adds a workspace without replacing that existing global surface.
  const allowedTabs: readonly string[] = isSuperadmin && actions.length === 0
    ? PLATFORM_TABS.filter(tab => !singleTenantLocked || !["platform-dashboard", "platform", "organizations"].includes(tab))
    : grantOnly ? (singleTenantLocked ? ["granted"] : ["granted", "organizations"]) : governanceOnly ? ["organizations"] : baseTabs.filter((tabName) => {
    if (tabName === "granted") return hasGrants;
    if (tabName === "platform-dashboard") return isSuperadmin && !singleTenantLocked;
    if (tabName === "usage") return canManageMakerspace;
    if (tabName === "dashboard") return handoutOnly || isSuperadmin || canSeeDashboard;
    // Personal rows and read state admit machine-only and handover staff.
    if (tabName === "notifications") return isSuperadmin || actions.length > 0;
    // Personal delivery channels belong to a staff account, not to the space.
    if (tabName === "channels") return !isSuperadmin && actions.length > 0;
    if (tabName === "tobuy") return canUseToBuy;
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
    if (tabName === "audit") return canViewAudit;
    if (tabName === "accountability") return canViewAudit;
    if (tabName === "reports") return canViewFinance || canViewAudit || canSeePrinting || canManageMachines || canManageEvents || canManageBookings;
    if (tabName === "warranty") return canEditInventory || canSeePrinting;
    if (tabName === "users") return canManageMakerspace;
    if (tabName === "settings") return canManageMakerspace;
    // The backend narrows further: only this space's Space Manager or a platform superadmin.
    if (tabName === "security") return canManageMakerspace;
    if (tabName === "emailtemplates") return canEditInventory || canSeePrinting || has("manage_devices") || canManageEvents || canManageBookings;
    if (tabName === "email-logs") return canManageMakerspace;
    if (tabName === "platform") return isSuperadmin && !singleTenantLocked;
    // #128 C-10: the Space Manager switches modules on and off (data kept); the server
    // keeps limit-gated installs on the managed platform for the superadmin.
    if (tabName === "modules") return canManageMakerspace;
    if (tabName === "devices") return has("manage_devices");
    if (tabName === "machines") return canManageMachines;
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
    // Event Managers settle registration fees by hand when the online rail is off; the
    // panel narrows them to event-registration charges (PaymentsPanel `eventOnly`).
    if (tabName === "payments") return canViewFinance || canRecordPayment || canManageEvents;
    // Mirrors `refund_case_access.may_read_queue`: finance reads every case, each domain's
    // staff read the cases for the charges they own. Cash-recording alone is not enough.
    if (tabName === "refunds") return canViewFinance || canManageEvents || canManageBookings || canManageMachines
      || canManageMembers || canManageMakerspace;
    // #100: each area's manager sees that area's money; the server narrows every list.
    if (tabName === "finance") return canViewFinance || canRecordPayment || canEditInventory || canManageBookings
      || canManageMachines || canManageEvents;
    if (tabName === "exports") return canManageMakerspace;
    if (tabName === "backups") return canManageMakerspace;
    if (tabName === "migration") return isSuperadmin;
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
    canManageQr,
    canManageMakerspace,
    canUseMemberCards,
    canManageMembers,
    canViewFinance,
    canRecordPayment,
    canManageMachines,
    canManageEvents,
    canManageBookings,
    canCollectServiceRequests,
    canChooseToBuyKind,
    allowedTabs,
    // The backend serves handover-only actors an operational queue home.
    defaultTab: allowedTabs.includes("dashboard") ? "dashboard" : (allowedTabs[0] ?? "dashboard"),
  };
}
