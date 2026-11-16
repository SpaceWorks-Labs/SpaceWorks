import { t } from "@lingui/core/macro";

import { ListLayout } from "../../../components/layouts";
import { DataTable, StatusBadge, type DataTableColumn } from "../../../components/ui";
import type { Tab } from "../../../components/ui";
import { formatDateTime, formatNumber, formatPercent } from "../../../lib/format";
import { useOrganizedAttendance, type OrganizedAttendanceRow } from "../organizedEventsApi";
import { opsQueryState, opsStatusLabel } from "../opsPresentation";

/** "—" when nobody registered: a rate over zero people is not 0 %. */
export function attendanceRateText(rate: number | null) {
  return rate === null ? "—" : formatPercent(rate / 100, { maximumFractionDigits: 1 });
}

/**
 * A25: how many people registered for and attended every event the organizer's organizations ran,
 * wherever it ran. Counts only -- the endpoint sends no attendee, contact or payment data, so a
 * partner venue stays opaque beyond its name.
 */
export function OrganizedAttendanceTable({ tabs, activeTab }: { tabs: Tab[]; activeTab: string }) {
  const attendance = useOrganizedAttendance(true);
  const rows = attendance.data?.results ?? [];
  const totals = attendance.data?.totals;
  const columns: DataTableColumn<OrganizedAttendanceRow>[] = [
    { key: "title", header: t`Event`, phone: "title" },
    { key: "venue_name", header: t`Venue` },
    { key: "starts_at", header: t`Starts`, render: row => formatDateTime(row.starts_at) },
    { key: "status", header: t`Status`, phone: "status", render: row => <StatusBadge domain="event" status={row.status} label={opsStatusLabel(row.status)} /> },
    { key: "registered", header: t`Registered`, className: "tabular-nums", render: row => formatNumber(row.registered) },
    { key: "attended", header: t`Attended`, className: "tabular-nums", render: row => formatNumber(row.attended) },
    { key: "attendance_rate_percent", header: t`Attendance rate`, className: "tabular-nums", render: row => attendanceRateText(row.attendance_rate_percent) },
  ];
  const overall = totals?.registered ? (100 * totals.attended) / totals.registered : null;
  return <ListLayout header={{ title: t`Organized events`, subtitle: t`Registered and attended counts for every event your organization ran, across spaces.` }}
    state={opsQueryState(attendance, t`attendance`)} tabs={tabs} activeTab={activeTab} isEmpty={attendance.isSuccess && !rows.length}
    empty={{ message: t`No attendance yet. Events your organization runs will appear here.` }}
    stats={totals ? [
      { label: t`Events`, value: formatNumber(totals.events) },
      { label: t`Registered`, value: formatNumber(totals.registered) },
      { label: t`Attended`, value: formatNumber(totals.attended) },
      { label: t`Attendance rate`, value: overall === null ? "—" : attendanceRateText(Math.round(overall * 10) / 10) },
    ] : []}
    callout={attendance.data?.truncated ? { size: "inline", tone: "warn", lead: t`Showing the latest ${rows.length} events only.`,
      body: t`Older events are left out of this table and its totals.` } : undefined}
    body={{ kind: "table", table: <DataTable<OrganizedAttendanceRow> caption={t`Attendance by event`} columns={columns} data={rows} getRowId={row => row.event_id} /> }} />;
}
