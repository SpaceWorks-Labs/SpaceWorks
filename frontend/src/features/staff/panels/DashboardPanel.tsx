import { Panel, useStaffGet, type Makerspace } from "./shared";
import { Link } from "react-router-dom";
import { dashboardDestination, dashboardHref } from "./dashboardLinks";
import { filterTabsByEnabledModules } from "../staffTabs";

type DashboardCounts = {
  upcoming_events?: number;
  pending_event_registrations?: number;
  pending_bookings?: number;
  upcoming_bookings?: number;
  scope_mode: "machine" | "full";
  overdue_loans?: number;
  pending_requests?: number;
  awaiting_issue?: number;
  open_problem_reports?: number;
  low_stock?: number;
  pending_prints?: number;
  active_prints?: number;
  prints_awaiting_collection?: number;
  failed_emails?: number;
  stocktakes_awaiting_approval?: number;
  warranty_expiring?: number;
  maintenance_overdue?: number;
  pending_payments?: number;
};

// Tiles keep their semantic intent; only emphasis is a filled attention pill.
// Numbers and labels otherwise sit on neutral panels.
type Tone = "accent" | "emphasis" | "success" | "warn" | "danger";

type Tile = {
  key: Exclude<keyof DashboardCounts, "scope_mode">;
  label: string;
  actionNeeded: boolean;
  tone: Tone;
};

const TILES: Tile[] = [
  { key: "upcoming_events", label: "Upcoming events", actionNeeded: false, tone: "accent" },
  { key: "pending_event_registrations", label: "Registrations awaiting approval", actionNeeded: true, tone: "warn" },
  { key: "pending_bookings", label: "Bookings awaiting approval", actionNeeded: true, tone: "warn" },
  { key: "upcoming_bookings", label: "Upcoming bookings", actionNeeded: false, tone: "accent" },
  { key: "overdue_loans", label: "Overdue loans", actionNeeded: true, tone: "danger" },
  { key: "pending_requests", label: "Pending requests", actionNeeded: true, tone: "warn" },
  { key: "awaiting_issue", label: "Awaiting issue", actionNeeded: true, tone: "warn" },
  { key: "open_problem_reports", label: "Problem reports", actionNeeded: true, tone: "danger" },
  { key: "low_stock", label: "Out of stock", actionNeeded: true, tone: "danger" },
  { key: "pending_prints", label: "Pending prints", actionNeeded: false, tone: "warn" },
  { key: "active_prints", label: "Active prints", actionNeeded: false, tone: "accent" },
  { key: "prints_awaiting_collection", label: "Ready to collect", actionNeeded: false, tone: "success" },
  { key: "failed_emails", label: "Failed emails", actionNeeded: true, tone: "danger" },
  { key: "stocktakes_awaiting_approval", label: "Stocktakes awaiting approval", actionNeeded: true, tone: "warn" },
  { key: "warranty_expiring", label: "Warranties expiring", actionNeeded: true, tone: "warn" },
  { key: "maintenance_overdue", label: "Maintenance overdue", actionNeeded: true, tone: "danger" },
  { key: "pending_payments", label: "Pending payments", actionNeeded: true, tone: "emphasis" },
];

const MACHINE_TILE_KEYS = new Set<Tile["key"]>([
  "pending_prints",
  "active_prints",
  "prints_awaiting_collection",
  "warranty_expiring",
  "maintenance_overdue",
]);

export function DashboardPanel({ makerspace, canManageMakerspace, allowedTabs, singleTenantLocked = false, guestOnly = false }: { makerspace: Makerspace; canManageMakerspace: boolean; allowedTabs?: readonly string[]; singleTenantLocked?: boolean; guestOnly?: boolean }) {
  const dashboard = useStaffGet<DashboardCounts>(
    ["dashboard", makerspace.id],
    `/admin/makerspace/${makerspace.id}/dashboard`,
  );

  return (
    <Panel title="Dashboard">
      {dashboard.isLoading ? <p className="mb-3 text-sm text-muted">Loading dashboard...</p> : null}
      {dashboard.error ? <p className="mb-3 text-sm text-danger">{dashboard.error.message}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {TILES.filter((tile) => (
          (dashboard.data?.scope_mode !== "machine" || MACHINE_TILE_KEYS.has(tile.key))
          && filterTabsByEnabledModules([dashboardDestination(tile.key).tab], makerspace).length > 0
          && (tile.key !== "failed_emails" || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("email"))
          && (tile.key !== "pending_payments" || canManageMakerspace || allowedTabs?.includes("payments"))
          && (!allowedTabs || allowedTabs.includes(dashboardDestination(tile.key).tab))
          && (!tile.key.includes("prints") || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("printing"))
          && (tile.key !== "maintenance_overdue" || makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("maintenance"))
        )).map((tile) => {
          const value = dashboard.data?.[tile.key] ?? 0;
          const needsAttention = tile.actionNeeded && value > 0;
          return (
            <Link
              key={tile.key}
              to={dashboardHref(tile.key, makerspace.slug, singleTenantLocked, guestOnly)}
              aria-label={`${tile.label}: ${value}. View list`}
              className="flex min-h-24 flex-col items-start justify-center gap-1 rounded-xl border border-line bg-panel p-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              <span className={`font-display tabular-nums text-[32px] leading-[38px] font-extrabold text-ink ${needsAttention && tile.tone === "emphasis" ? "rounded-full bg-emphasis px-2 text-on-emphasis" : ""}`}>
                {value}
              </span>
              <span className="eyebrow">{tile.label}</span>
            </Link>
          );
        })}
      </div>
    </Panel>
  );
}
