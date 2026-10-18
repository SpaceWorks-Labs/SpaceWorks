import { createContext, useContext, type ReactNode } from "react";
import { Panel } from "./shared";
import type { ReportCatalogItem } from "./operationsReportsConfig";

const HARDWARE = ["most-lent", "top-borrowers", "damaged-missing", "damaged-lost", "recently-added", "taken-items", "active-loans", "returns", "qr-scans", "member-activity", "fablab-health", "machine-usage", "event-attendance", "booking-utilization", "maintenance-activity"];
const FINANCE = ["payments-ledger", "payment-reconciliation", "revenue-over-time", "cash-book", "accounting-journal"];
const COVERAGE = ["loan-throughput", "inventory-control", "evidence-compliance", "import-quality", "procurement-performance", "communications-health", "community-engagement", "module-operational-health", "certification-coverage"];
type Selection = { selected: string | null; columns: string[]; catalog: ReportCatalogItem[]; specialists: Set<string>; preferGeneric: boolean };
const Context = createContext<Selection | null>(null);
const normalize = (title: string) => title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const ALIASES: Record<string, string> = { "bookable-space-utilization": "booking-utilization", bookings: "booking-utilization",
  "events-attendance": "event-attendance", events: "event-attendance", maintenance: "maintenance-activity" };

/** Query-owning report components stay mounted; inactive presentation is unmounted here. */
export function ReportSelectionProvider({ selected, columns, catalog, hardware, finance, machines, grain = "day", children }: {
  selected: string | null; columns: string[]; catalog: ReportCatalogItem[]; hardware: boolean; finance: boolean; machines: boolean; grain?: string; children: ReactNode;
}) {
  const specialists = new Set([...COVERAGE, ...(hardware ? HARDWARE : []), ...(finance ? FINANCE : []), ...(machines ? ["machine-service", "printer-service"] : [])]);
  const preferGeneric = selected !== null && (Boolean(catalog.find((report) => report.key === selected)?.chart_spec)
    || (HARDWARE.includes(selected) && grain !== "day"));
  if (preferGeneric && selected) specialists.delete(selected);
  return <Context.Provider value={{ selected, columns, catalog, specialists, preferGeneric }}>{children}</Context.Provider>;
}
export function useReportColumns() { return useContext(Context)?.columns ?? []; }
export function SelectedReportPanel({ title, reportKey, generic = false, children }: {
  title: string; reportKey?: string; generic?: boolean; children: ReactNode;
}) {
  const selection = useContext(Context);
  const normalized = normalize(title);
  const key = reportKey ?? selection?.catalog.find(report => normalize(report.title) === normalized)?.key ?? ALIASES[normalized] ?? normalized;
  if (selection?.selected && (key !== selection.selected || (generic && selection.specialists.has(key)) || (!generic && selection.preferGeneric))) return null;
  return <div className="mt-6 min-w-0"><Panel title={title}>{children}</Panel></div>;
}
