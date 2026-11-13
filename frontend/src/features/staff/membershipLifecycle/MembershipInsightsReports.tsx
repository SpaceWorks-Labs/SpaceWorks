import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { SegmentedControl } from "../../../components/ui";
import { lifecycleApi, lifecycleKeys } from "../membershipLifecycleApi";
import { useAnalyticsCatalog } from "../panels/analyticsApi";
import { ReportChartResult } from "../panels/ReportAreaSections";

// Parity O-B3 report keys (`operations/report_definitions_org_parity.py`), in the order the tabs show them.
// The two leagues (part 2) need `membership.units`; the catalogue leaves them out while it is off.
const KEYS = ["membership-revenue-by-plan", "membership-renewal-forecast", "membership-approval-times",
  "membership-unit-league", "membership-level-league"] as const;
type Key = (typeof KEYS)[number];
const FORECAST: Key = "membership-renewal-forecast";

const tabLabel = (key: Key) => ({
  "membership-revenue-by-plan": t`Revenue by plan`,
  "membership-renewal-forecast": t`Renewal forecast`,
  "membership-approval-times": t`Approval times`,
  "membership-unit-league": t`Unit league`,
  "membership-level-league": t`Level league`,
})[key];
const explain = (key: Key) => ({
  "membership-revenue-by-plan": t`Money collected on membership charges per month and plan, less refunds that went back. Flat dues with no plan behind them show under a blank plan. Currencies are never added together.`,
  "membership-renewal-forecast": t`Current terms on renewing plans that end within 30, 60 and 90 days (each includes the shorter ones), at the plan's renewal price. This is money falling due, not a guess at what will be collected.`,
  "membership-approval-times": t`Join requests decided in each period, with the median and the 90th-percentile wait from asking to the decision, in hours. One slow case shows up rather than being averaged away.`,
  "membership-unit-league": t`Each unit with its members today (its whole subtree and directly), who joined in the period, and join requests still waiting. Counts only, never names.`,
  "membership-level-league": t`Each unit level (for example chapter or region) with how many units it has, their members today, who joined in the period, and join requests still waiting.`,
})[key];
const grainLabel = (grain: string) => (grain === "week" ? t`By week` : grain === "day" ? t`By day` : t`By month`);

/**
 * Revenue by plan, the 30/60/90-day renewal forecast, approval times and the unit and level leagues, under Membership › Insights. Each tab is
 * one catalogue report drawn from its own chart spec; a report the caller may not run (or whose switch is off)
 * is simply not offered, and with none left the whole block is absent.
 */
export function MembershipInsightsReports({ makerspaceId }: { makerspaceId: number }) {
  const catalog = useAnalyticsCatalog(makerspaceId);
  const fy = useQuery({ queryKey: lifecycleKeys.financialYear(makerspaceId), queryFn: () => lifecycleApi.financialYear(makerspaceId) });
  const [selected, setSelected] = useState<string>("");
  const [preset, setPreset] = useState("");
  const [grain, setGrain] = useState("month");
  const reports = KEYS.flatMap((key) => {
    const entry = catalog.data?.results.find((report) => report.key === key && report.available !== false && report.previewable !== false);
    return entry ? [{ key, entry }] : [];
  });
  const current = reports.find((report) => report.key === selected) ?? reports[0];
  if (catalog.isLoading) return <LogoLoader label={t`Loading membership reports…`} size={48} className="min-h-16 py-3" />;
  if (!current) return null;
  const range = fy.data?.presets.find((row) => row.key === preset) ?? fy.data?.presets[0];
  const dated = current.key !== FORECAST;
  const period = { start: dated ? range?.start ?? "" : "", end: dated ? range?.end ?? "" : "", grain };
  const grains = current.entry.grains ?? [];
  return <section className="grid min-w-0 gap-4 rounded-xl border border-line bg-panel p-4" aria-labelledby="membership-reports-heading">
    <h3 id="membership-reports-heading" className="title-section">{t`Membership reports`}</h3>
    {reports.length > 1 ? <SegmentedControl label={t`Membership report`} value={current.key}
      options={reports.map((report) => ({ value: report.key, label: tabLabel(report.key) }))} onChange={setSelected} /> : null}
    <div className="flex flex-wrap items-end gap-3">
      {dated && fy.data ? <label className="grid gap-1 text-sm">{t`Financial year`}
        <select className="desk-input max-w-full" value={range?.key ?? ""} onChange={(event) => setPreset(event.target.value)}>
          {fy.data.presets.map((row) => <option key={row.key} value={row.key}>{row.label}</option>)}
        </select></label> : null}
      {grains.length > 1 ? <label className="grid gap-1 text-sm">{t`Group`}
        <select className="desk-input max-w-full" value={grains.includes(grain) ? grain : grains[0]} onChange={(event) => setGrain(event.target.value)}>
          {grains.map((value) => <option key={value} value={value}>{grainLabel(value)}</option>)}
        </select></label> : null}
    </div>
    <p className="max-w-prose text-sm text-muted">{explain(current.key)}</p>
    <ReportChartResult key={current.key} report={current.entry} base={`/admin/makerspace/${makerspaceId}/analytics`}
      period={period} makerspaceId={makerspaceId} />
  </section>;
}
