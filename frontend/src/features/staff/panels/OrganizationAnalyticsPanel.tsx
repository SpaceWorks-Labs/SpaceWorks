import { useState } from "react";
import { DashboardLayout } from "../../../components/layouts";
import { EmptyState, ErrorText, Pagination } from "../../../components/ui";
import { useOrganizationAnalytics } from "../organizationAnalyticsApi";
import { useOrganizations } from "../organizationsApi";
import { adminQueryState } from "../adminPresentation";
import { organizationReportChoices, organizationReportTitle, organizationChartHint, organizationReportGrains } from "../organizationReportChoices";
import { AnalyticsData } from "./AnalyticsData";
import { AnalyticsPeriodControls } from "./AnalyticsPeriodControls";
import type { AnalyticsPeriod } from "./analyticsApi";
import type { Makerspace } from "./shared";

export function OrganizationAnalyticsPanel({ makerspaces }: { makerspaces: Makerspace[] }) {
  const [organizationValue, setOrganizationValue] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [page, setPage] = useState(1);
  const organizations = useOrganizations(page);
  const [reportKey, setReportKey] = useState("summary");
  const [period, setPeriod] = useState<AnalyticsPeriod>({ start: "", end: "", grain: "day" });
  const parsed = Number(organizationValue);
  const organizationId = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
  const report = useOrganizationAnalytics(organizationId, reportKey, period);
  const choices = organizations.data?.results ?? [];
  const title = organizationReportTitle(reportKey);
  const spec = report.data?.chart_spec;
  const hint = organizationChartHint(reportKey);
  // Do not present cached personal/tenant data after an authorization failure.
  const data = report.isError ? undefined : report.data;
  return <DashboardLayout header={{ title: "Organization analytics", eyebrow: "Across your spaces",
    subtitle: "Combined counts with their per-makerspace breakdown. Currencies and measurement units stay separate.",
    meta: <div className="grid gap-4"><div className="flex flex-wrap items-end gap-4">
      <label className="grid min-w-0 gap-2 text-sm">Organization<select className="desk-input max-w-full" value={organizationValue} onChange={event => {
        setOrganizationValue(event.target.value);
        setOrganizationName(choices.find(org => String(org.id) === event.target.value)?.name ?? "");
      }}><option value="">Choose an organization</option>
        {organizationValue && !choices.some(org => String(org.id) === organizationValue) ? <option value={organizationValue}>{organizationName}</option> : null}
        {choices.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}
      </select></label>
      <label className="grid gap-2 text-sm">Report<select className="desk-input max-w-full" value={reportKey} onChange={event => setReportKey(event.target.value)}>
        {organizationReportChoices.map(key => <option key={key} value={key}>{organizationReportTitle(key)}</option>)}
      </select></label>
    </div>
      <AnalyticsPeriodControls value={period} onChange={setPeriod} grains={organizationReportGrains(reportKey)} />
      {organizations.isLoading ? <p role="status">Loading organizations?</p> : null}
      {organizations.isError ? <ErrorText resource="organizations" onRetry={() => void organizations.refetch()} /> : null}
      {organizations.isSuccess && !choices.length ? <p>No organizations available.</p> : null}
      {organizations.data && (organizations.data.next || organizations.data.previous) ? <Pagination page={page} totalPages={Math.ceil(organizations.data.count / 24)} onChange={setPage} /> : null}
    </div> }}
    stats={[]} state={organizationId ? adminQueryState(report, "organization analytics") : { status: "ready" }}
    main={[
      { title: "Organization total", empty: { message: "No combined activity in this period." },
        content: organizationId === null ? <EmptyState message="Pick an organization to see its numbers." />
          : data ? <AnalyticsData title={`${title} ? organization total`} rows={data.total.rows} spec={spec} hint={hint} /> : null },
      ...(organizationId && data ? [{ title: "Breakdown by makerspace", empty: { message: "This organization doesn't own any spaces with reports yet." },
        isEmpty: !data.breakdown.length, content: <div className="grid gap-6">{data.breakdown.map(entry => {
          const name = makerspaces.find(space => space.id === entry.makerspace_id)?.name ?? `Makerspace #${entry.makerspace_id}`;
          return <section key={entry.makerspace_id}><h3 className="title-section mb-3">{name}</h3>
            <AnalyticsData title={`${title} ? ${name}`} rows={entry.rows} spec={spec} hint={hint} />
          </section>;
        })}</div> }] : []),
    ]} />;
}
