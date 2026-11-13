import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useAnalyticsCatalog } from "./analyticsApi";
import { ReportChartResult } from "./ReportAreaSections";
import { staffTabPath } from "../staffTabs";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import type { Makerspace } from "./shared";
import { LogoLoader } from "../../../components/LogoLoader";

const CONSOLES: Record<string, { modules: string[]; keys: string[] }> = {
  inventory: { modules: ["public_inventory"], keys: ["inventory-utilisation", "most-lent", "stock-health", "consumable-pools"] },
  machines: { modules: ["machines"], keys: ["machine-usage", "machine-downtime", "machine-usage-heatmap", "machine-service", "service-queue-times", "machine-errors", "printer-jobs", "consumable-usage", "consumable-pools", "maintenance-activity", "warranty-expiry", "machine-access-grants"] },
  bookings: { modules: ["bookings"], keys: ["booking-utilization", "booking-occupancy", "booking-lead-time"] },
  events: { modules: ["events"], keys: ["event-funnel", "event-signups", "event-revenue", "event-checkin-times", "event-feedback-scores", "event-certificates-issued"] },
  members: { modules: ["membership"], keys: ["membership-growth", "member-retention", "membership-revenue", "membership-revenue-by-plan", "membership-renewal-forecast", "presence-activity"] },
  payments: { modules: [], keys: ["revenue-over-time", "payments-ageing", "payment-reconciliation", "cash-book", "cash-in-hand"] },
  notifications: { modules: ["notifications"], keys: ["communications-health"] },
  "email-logs": { modules: [], keys: ["communications-health"] },
  communications: { modules: [], keys: ["communications-health"] },
  devices: { modules: ["devices"], keys: ["device-health", "device-adapter-activity"] },
  cards: { modules: ["membership"], keys: ["member-card-issuance", "card-studio-activity"] },
  shop: { modules: ["shop"], keys: ["shop-sales", "shop-product-sales", "shop-stock-value"] },
};

// The module group (the same keys as the module switches) each console's reports sit under in the Reports hub.
const HUB_GROUPS: Record<string, string> = {
  inventory: "inventory", machines: "machines", bookings: "bookings", events: "events", members: "membership", cards: "membership",
  payments: "payments", notifications: "notifications", "email-logs": "notifications", communications: "notifications",
  devices: "devices", shop: "shop",
};

export function ModuleAnalytics({ makerspace, tab, singleTenantLocked = false, guestOnly = false }: {
  makerspace: Makerspace; tab: string; singleTenantLocked?: boolean; guestOnly?: boolean;
}) {
  const config = CONSOLES[tab];
  const enabled = Boolean(!guestOnly && config && makerspace.enabled_modules?.includes("reports")
    && config.modules.every(module => makerspace.enabled_modules?.includes(module)));
  const catalog = useAnalyticsCatalog(makerspace.id, enabled);
  const [selected, setSelected] = useState("");
  if (!enabled) return null;
  const reports = catalog.data?.results.filter(report => config.keys.includes(report.key) && report.available !== false && report.previewable !== false) ?? [];
  const report = reports.find(entry => entry.key === selected) ?? reports[0];
  if (catalog.isSuccess && !report) return null;
  return <section aria-label={t`Module analytics`} className="mt-6 min-w-0 rounded-xl border border-line bg-panel p-4">
    <h2 className="title-panel">{t`At a glance`}</h2>
    {catalog.isLoading ? <LogoLoader label={t`Loading analytics…`} size={48} className="min-h-16 py-3" /> : catalog.isError ? <div role="alert"><p>{t`Couldn't load analytics.`}</p><button type="button" className="desk-button" onClick={() => void catalog.refetch()}>{t`Retry`}</button></div> : report ? <>
      <label className="my-3 grid gap-2 text-sm">{t`Analytics report`}<select className="desk-input max-w-full" value={report.key} onChange={event => setSelected(event.target.value)}>
        {reports.map(entry => <option key={entry.key} value={entry.key}>{entry.title}</option>)}
      </select></label>
      <ReportChartResult report={report} base={`/admin/makerspace/${makerspace.id}/analytics`} makerspaceId={makerspace.id}
        period={{ start: "", end: "", grain: report.grains[0] ?? "day" }} />
      <a className="desk-button mt-3" href={consoleSessionHref(`${staffTabPath("reports", guestOnly, makerspace.slug, singleTenantLocked)}?report=${encodeURIComponent(report.key)}`)}>{t`Open in reports`}</a>
      <a className="desk-button mt-3 ml-2" href={consoleSessionHref(`${staffTabPath("reports", guestOnly, makerspace.slug, singleTenantLocked)}?group=${HUB_GROUPS[tab] ?? ""}`)}>{t`All reports for this module`}</a>
    </> : null}
  </section>;
}
