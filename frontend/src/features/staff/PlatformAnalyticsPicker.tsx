import { useState } from "react";
import { Pagination } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { useAnalyticsMakerspaces, type AnalyticsMakerspace } from "./platformAnalyticsApi";
import { ReportAreaSections } from "./panels/ReportAreaSections";
import { useAnalyticsCatalog, type AnalyticsPeriod } from "./panels/analyticsApi";

export function PlatformAnalyticsPicker({ period }: { period: AnalyticsPeriod }) {
  const [page, setPage] = useState(1);
  const [pickerReport, setPickerReport] = useState("summary");
  const [space, setSpace] = useState<AnalyticsMakerspace | null>(null);
  const spaces = useAnalyticsMakerspaces(page, pickerReport);
  return <section aria-label="Makerspace analytics" className="min-w-0 space-y-3 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section">Makerspace analytics</h3>
    <label className="grid gap-2 text-sm">Picker report scope<select className="desk-input" value={pickerReport} onChange={event => { setPickerReport(event.target.value); setPage(1); setSpace(null); }}>
      {["summary", "machine-usage", "booking-utilization", "event-funnel", "membership-growth", "revenue-over-time", "communications-health",
        "mobile-devices", "device-health", "presence-activity", "audit-activity"].map(key => <option key={key} value={key}>{key.replace(/-/g, " ")}</option>)}
    </select></label>
    <label className="grid gap-2 text-sm">Makerspace<select className="desk-input" value={space?.id ?? ""} onChange={event => setSpace(spaces.data?.results.find(row => row.id === Number(event.target.value)) ?? null)}>
      <option value="">Choose a makerspace</option>
      {space && !spaces.data?.results.some(row => row.id === space.id) ? <option value={space.id}>{space.name}</option> : null}
      {spaces.data?.results.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
    </select></label>
    {spaces.isLoading ? <p role="status">Loading makerspaces…</p> : spaces.isError ? <div role="alert"><p>Couldn't load the makerspace picker.</p><button type="button" className="desk-button" onClick={() => void spaces.refetch()}>Retry</button></div> : !spaces.data?.results.length ? <p>No makerspaces are available for this report.</p> : null}
    {spaces.data && (spaces.data.next || spaces.data.previous) ? <Pagination page={page} totalPages={Math.ceil(spaces.data.count / 24)} onChange={setPage} /> : null}
    {space ? <TenantAnalytics key={space.id} space={space} period={period} initialReport={pickerReport} /> : <p className="text-sm text-muted">Choose a space to open its scoped analytics.</p>}
  </section>;
}
function TenantAnalytics({ space, period, initialReport }: { space: AnalyticsMakerspace; period: AnalyticsPeriod; initialReport: string }) {
  const catalog = useAnalyticsCatalog(space.id);
  const [selected, setSelected] = useState(initialReport);
  if (catalog.isLoading) return <p role="status">Loading this makerspace's reports…</p>;
  if (catalog.isError) return <div role="alert"><p>{catalog.error instanceof StructuredApiError && catalog.error.status === 403
    ? "Access to this makerspace's analytics is blocked. Your account needs local authority for this report."
    : "Couldn't load this makerspace's analytics."}</p><button type="button" className="desk-button" onClick={() => void catalog.refetch()}>Retry</button></div>;
  const reports = catalog.data?.results ?? [];
  if (!reports.length) return <p>No reports available for this makerspace.</p>;
  return <div className="min-w-0 space-y-4">
    <a className="desk-button" href={`/m/${space.slug}/admin/reports?report=${encodeURIComponent(selected || initialReport)}`}>Open {space.name} reports</a>
    <a className="desk-button ml-2" href={`/m/${space.slug}/admin/dashboard`}>Open {space.name} dashboard</a>
    <ReportAreaSections reports={reports} selected={!selected || reports.some(row => row.key === selected) ? selected : reports[0].key}
      onSelect={setSelected} period={period} makerspaceId={space.id} base={`/admin/makerspace/${space.id}/analytics`} />
  </div>;
}
