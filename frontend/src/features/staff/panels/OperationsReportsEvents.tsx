import { t } from "@lingui/core/macro";
import { SelectedReportPanel as Panel } from "./OperationsReportSelection";
import { BarChart, DataState, LineChart, PieChart, ReportTable, StatCards } from "./OperationsReportsParts";

import { groupReportByMakerspace, sum, useFablabReport, type EventAttendanceRow, type FablabPanelProps, type ReportResponse } from "./operationsReportsFablabApi";

export function OperationsReportsEvents(props: FablabPanelProps) {
  const query = useFablabReport<EventAttendanceRow>("event-attendance", props);
  if (!props.enabled) return <Panel title={t`Events`}><p className="text-sm text-muted">{t`Module disabled`}</p></Panel>;
  const rows = query.data?.typed_rows ?? [];
  const groups = groupReportByMakerspace(query.data);
  return (
    <Panel title={t`Events attendance`}>
      <DataState loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} empty={!rows.length}>
        {props.aggregate ? <div className="mt-4 space-y-6">{groups.map((group) => (
          <section key={group.makerspaceId} className="rounded-md border border-line p-4">
            <h4 className="eyebrow">{props.makerspaceName(group.makerspaceId)}</h4>
            <EventsReport rows={group.rows} data={group.data} />
          </section>
        ))}</div> : <EventsReport rows={rows} data={query.data} />}
      </DataState>
    </Panel>
  );
}

function EventsReport({ rows, data }: { rows: EventAttendanceRow[]; data?: ReportResponse<EventAttendanceRow> }) {
  const statusRows = ["pending_approval", "registered", "waitlisted", "rejected", "cancelled", "attended"].map((key) => ({ label: key, value: sum(rows, key) }));
  return <>
    <StatCards stats={[["Events", rows.length], ["Registrations", sum(rows, "registrations")], ["Confirmed", sum(rows, "confirmed")], ["Attended", sum(rows, "attended")]]} />
    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <PieChart rows={statusRows} valueLabel="registrations" />
      <BarChart rows={rows.filter((row) => row.attendance_rate_percent !== null).map((row) => ({ label: row.title, value: row.attendance_rate_percent ?? 0 }))} valueLabel="% attended" />
      <LineChart rows={[...rows].sort((a, b) => a.starts_at.localeCompare(b.starts_at)).map((row) => ({ label: row.starts_at, value: row.registrations }))} valueLabel="registrations" />
    </div>
    <ReportTable data={data} />
  </>;
}
