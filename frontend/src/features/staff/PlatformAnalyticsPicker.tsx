import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Pagination } from "../../components/ui";
import { useAnalyticsMakerspaces, type AnalyticsMakerspace } from "./platformAnalyticsApi";
import type { AnalyticsPeriod } from "./panels/analyticsApi";
import { PlatformTenantAnalytics } from "./PlatformTenantAnalytics";
import { LogoLoader } from "../../components/LogoLoader";

export function PlatformAnalyticsPicker({ period }: { period: AnalyticsPeriod }) {
  const [page, setPage] = useState(1);
  const [pickerReport, setPickerReport] = useState("summary");
  const [space, setSpace] = useState<AnalyticsMakerspace | null>(null);
  const spaces = useAnalyticsMakerspaces(page, pickerReport);
  return <section aria-label={t`Makerspace analytics`} className="min-w-0 space-y-3 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">{t`Makerspace analytics`}</h3>
    <label className="grid gap-2 text-sm">{t`Picker report scope`}<select className="desk-input" value={pickerReport} onChange={event => { setPickerReport(event.target.value); setPage(1); setSpace(null); }}>
      {["summary", "machine-usage", "booking-utilization", "event-funnel", "membership-growth", "revenue-over-time", "communications-health",
        "mobile-devices", "device-health", "presence-activity", "audit-activity"].map(key => <option key={key} value={key}>{key.replace(/-/g, " ")}</option>)}
    </select></label>
    <label className="grid gap-2 text-sm">{t`Makerspace`}<select className="desk-input" value={space?.id ?? ""} onChange={event => setSpace(spaces.data?.results.find(row => row.id === Number(event.target.value)) ?? null)}>
      <option value="">{t`Choose a makerspace`}</option>
      {space && !spaces.data?.results.some(row => row.id === space.id) ? <option value={space.id}>{space.name}</option> : null}
      {spaces.data?.results.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
    </select></label>
    {spaces.isLoading ? <LogoLoader label={t`Loading makerspaces…`} size={48} className="min-h-16 py-3" /> : spaces.isError ? <div role="alert"><p>{t`Couldn't load the makerspace picker.`}</p><button type="button" className="desk-button" onClick={() => void spaces.refetch()}>{t`Retry`}</button></div> : !spaces.data?.results.length ? <p>{t`No makerspaces are available for this report.`}</p> : null}
    {spaces.data && (spaces.data.next || spaces.data.previous) ? <Pagination page={page} totalPages={Math.ceil(spaces.data.count / 24)} onChange={setPage} /> : null}
    {space ? <PlatformTenantAnalytics key={space.id} space={space} period={period} initialReport={pickerReport} /> : <p className="text-sm text-muted">{t`Choose a space to open its scoped analytics.`}</p>}
  </section>;
}
