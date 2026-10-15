import { useState } from "react";
import { DashboardLayout } from "../../../components/layouts";
import { DataTable, EmptyState, ErrorText, Pagination } from "../../../components/ui";
import { useOrganizationAnalytics, type OrganizationReportRows } from "../organizationAnalyticsApi";
import { useOrganizations } from "../organizationsApi";
import { adminQueryState } from "../adminPresentation";
import { STICKY_FIRST_COLUMN } from "../matrixColumns";
import { reportDefinitions, type ReportKey } from "./operationsReportsConfig";
import type { Makerspace } from "./shared";

export function OrganizationAnalyticsPanel({ makerspaces }: { makerspaces: Makerspace[] }) {
  const [organizationValue, setOrganizationValue] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [page, setPage] = useState(1);
  const organizations = useOrganizations(page);
  const [reportKey, setReportKey] = useState<ReportKey>("summary");
  const parsed = Number(organizationValue);
  const organizationId = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
  const report = useOrganizationAnalytics(organizationId, reportKey);
  const total = report.data?.total.rows[0] ?? {};
  const stats = Object.entries(total).filter(([, value]) => typeof value === "number").slice(0, 4)
    .map(([key, value]) => ({ label: key.replace(/_/g, " "), value: value as number }));
  const choices = organizations.data?.results ?? [];
  return <DashboardLayout header={{ title: "Organization analytics", eyebrow: "Across your spaces", subtitle: "Your organization's spaces, side by side.", meta: <div className="grid gap-4">
        <div className="flex flex-wrap items-end gap-4">
          <label className="grid min-w-0 gap-2 text-sm">Organization
            <select className="desk-input max-w-full" value={organizationValue} onChange={event => {
              setOrganizationValue(event.target.value);
              setOrganizationName(choices.find(org => String(org.id) === event.target.value)?.name ?? "");
            }}><option value="">Choose an organization</option>
              {organizationValue && !choices.some(org => String(org.id) === organizationValue) ? <option value={organizationValue}>{organizationName}</option> : null}
              {choices.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}
            </select>
          </label>
          <label className="grid gap-2 text-sm">Report
            <select className="desk-input max-w-full" value={reportKey} onChange={event => setReportKey(event.target.value as ReportKey)}>
              {reportDefinitions.filter(definition => definition.aggregate_supported).map(definition => <option key={definition.key} value={definition.key}>{definition.title}</option>)}
            </select>
          </label>
        </div>
        {organizations.isLoading ? <p role="status">Loading organizations…</p> : null}
        {organizations.isError ? <ErrorText resource="organizations" onRetry={() => { void organizations.refetch(); }} /> : null}
        {organizations.data && (organizations.data.next || organizations.data.previous) ? <Pagination page={page} totalPages={Math.ceil(organizations.data.count / 24)} onChange={setPage} /> : null}
      </div> }}
    state={organizationId ? adminQueryState(report, "organization analytics") : { status: "ready" }} stats={organizationId ? stats : []}
    main={[
      { title: "Breakdown by makerspace", empty: { message: "This organization doesn't own any spaces with reports yet." },
        content: organizationId === null ? <EmptyState message="Pick an organization to see its numbers." />
          : <ReportContent rows={report.data?.breakdown ?? []} makerspaces={makerspaces} /> },
      ...(organizationId && report.data?.breakdown.length ? [{ title: "Organization total", empty: { message: "No totals yet. Choose another report." },
        content: <AnalyticsRowsTable rows={report.data.total.rows} caption="Organization total report" /> }] : []),
    ]} />;
}

function ReportContent({ rows, makerspaces }: {
  rows: { makerspace_id: number; rows: OrganizationReportRows["rows"] }[]; makerspaces: Makerspace[];
}) {
  return rows.length ? <div className="grid gap-6">{rows.map(entry => {
    const name = makerspaces.find(space => space.id === entry.makerspace_id)?.name ?? `Makerspace #${entry.makerspace_id}`;
    return <section key={entry.makerspace_id}><h3 className="title-section mb-3">{name}</h3><AnalyticsRowsTable rows={entry.rows} caption={`${name} report`} /></section>;
  })}</div> : <EmptyState message="This organization doesn't own any spaces with reports yet." />;
}

function AnalyticsRowsTable({ rows, caption }: { rows: OrganizationReportRows["rows"]; caption: string }) {
  const headers = [...new Set(rows.flatMap(row => Object.keys(row)))];
  return <div role="region" aria-label={caption}><DataTable<OrganizationReportRows["rows"][number]> data={rows} getRowId={row => rows.indexOf(row)}
    emptyDescription="No records yet. Choose another report."
    columns={headers.map((header, index) => ({ key: header, header: header.replace(/_/g, " "), className: index === 0 ? STICKY_FIRST_COLUMN : undefined,
      render: row => formatCell(row[header]) }))} /></div>;
}
function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
