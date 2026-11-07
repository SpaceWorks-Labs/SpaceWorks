import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useAnalyticsCatalog } from "./analyticsApi";
import { ReportChartResult } from "./ReportAreaSections";
import { staffTabPath } from "../staffTabs";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import type { Makerspace } from "./shared";

const CONSOLES: Record<string, { modules: string[]; keys: string[] }> = {
  inventory: { modules: ["public_inventory"], keys: ["inventory-utilisation", "most-lent", "stock-health", "consumable-pools"] },
  machines: { modules: ["machines"], keys: ["machine-usage", "machine-downtime", "machine-usage-heatmap", "machine-service", "service-queue-times", "machine-errors", "printer-jobs", "consumable-usage", "consumable-pools", "maintenance-activity", "warranty-expiry"] },
  bookings: { modules: ["bookings"], keys: ["booking-utilization", "booking-occupancy", "booking-lead-time"] },
  events: { modules: ["events"], keys: ["event-funnel", "event-signups", "event-revenue", "event-checkin-times", "event-feedback-scores"] },
  members: { modules: ["membership"], keys: ["membership-growth", "member-retention", "membership-revenue", "presence-activity"] },
  payments: { modules: [], keys: ["revenue-over-time", "payments-ageing", "payment-reconciliation", "cash-book"] },
  notifications: { modules: ["notifications"], keys: ["communications-health"] },
  "email-logs": { modules: [], keys: ["communications-health"] },
  communications: { modules: [], keys: ["communications-health"] },
  devices: { modules: ["devices"], keys: ["device-health"] },
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
    {catalog.isLoading ? <p role="status">{t`Loading analytics…`}</p> : catalog.isError ? <div role="alert"><p>{t`Couldn't load analytics.`}</p><button type="button" className="desk-button" onClick={() => void catalog.refetch()}>{t`Retry`}</button></div> : report ? <>
      <label className="my-3 grid gap-2 text-sm">{t`Analytics report`}<select className="desk-input max-w-full" value={report.key} onChange={event => setSelected(event.target.value)}>
        {reports.map(entry => <option key={entry.key} value={entry.key}>{entry.title}</option>)}
      </select></label>
      <ReportChartResult report={report} base={`/admin/makerspace/${makerspace.id}/analytics`} makerspaceId={makerspace.id}
        period={{ start: "", end: "", grain: report.grains[0] ?? "day" }} />
      <a className="desk-button mt-3" href={consoleSessionHref(`${staffTabPath("reports", guestOnly, makerspace.slug, singleTenantLocked)}?report=${encodeURIComponent(report.key)}`)}>{t`Open in reports`}</a>
    </> : null}
  </section>;
}
