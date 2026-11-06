import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { ListLayout } from "../../../components/layouts";
import { DataTable, RelativeTime } from "../../../components/ui";
import { useUrlListState } from "../../../lib/useUrlListState";
import { ListViewControls } from "../ListViewControls";
import { AuditLogFilters, auditFilterParams, emptyAuditFilters, type AuditFilters } from "./AuditLogFilters";
import { AuditLogDetails } from "./AuditLogDetails";
import { AuditVerificationStatus } from "./AuditVerificationStatus";
import { useStaffGet } from "./shared";

type AuditLogEntry = {
  id: number; action: string; action_label: string; actor_display: string | null;
  target_type: string; target_id: string | number | null;
  meta: Record<string, unknown>; meta_redacted: boolean; created_at: string;
};
type AuditLogResponse = { count: number; next: string | null; previous: string | null; results: AuditLogEntry[] };

export function AuditLog({ makerspaceId }: { makerspaceId?: number }) {
  const list = useUrlListState({ ...emptyAuditFilters, makerspace: makerspaceId ? String(makerspaceId) : "", ordering: "-created_at", page: "1" });
  const filters: AuditFilters = list.values;
  const filterParams = auditFilterParams(filters);
  const params = new URLSearchParams(filterParams);
  params.set("page", String(list.page));
  params.set("ordering", list.values.ordering);
  const query = params.toString();
  const logs = useStaffGet<AuditLogResponse>(["audit", query], `/admin/audit-logs?${query}`);
  const clear = () => list.update({ ...emptyAuditFilters, makerspace: makerspaceId ? String(makerspaceId) : "" });
  const chips = Object.entries(filters).filter(([key, value]) => key in emptyAuditFilters && value && !(key === "makerspace" && value === String(makerspaceId)))
    .map(([key, value]) => ({ key, label: `${key.replace(/_/g, " ")}: ${value}`, onRemove: () => list.update({ [key]: "" }) }));

  return <ListLayout width="wide"
    header={{ title: t`Audit log`, subtitle: t`Every state change in this makerspace, append-only.`, meta: <AuditVerificationStatus key={new URLSearchParams(filterParams).toString()} makerspaceId={filters.makerspace} params={filterParams} /> }}
    state={{ status: logs.isLoading ? "loading" : logs.error ? "error" : "ready", error: t`Couldn't load audit entries${logs.error?.message ? ` (${logs.error.message})` : ""}. Try again.`, onRetry: () => void logs.refetch() }}
    isEmpty={Boolean(logs.data && !logs.data.results.length)} filtered={chips.length > 0}
    empty={{ message: t`No audit entries yet. Complete a workflow to start the trail.` }}
    filteredEmpty={{ message: t`No entries match these filters. Clear filters to see the trail.`, action: { label: t`Clear filters`, onClick: clear } }}
    filters={{ sort: makerspaceId ? <ListViewControls state={list} makerspaceId={makerspaceId} entity="audit" search={false} sorts={[["-created_at", "Newest"], ["created_at", "Oldest"], ["action", "Action"]]} /> : undefined,
      // Active filters stay visible (and removable) outside the closed popover.
      activeCount: chips.length, chips, controls: <AuditLogFilters filters={filters} onChange={next => list.update(next)} />, onClear: clear }}
    body={{ kind: "table", table: <DataTable data={logs.data?.results ?? []} listState={list}
      ordering={list.values.ordering} onOrderingChange={ordering => list.update({ ordering })}
      columns={[
        { key: "action", header: "Activity", sortable: true, render: log => <div><span className="font-semibold">{log.actor_display ?? t`System`}</span><p>{log.action_label}</p></div> },
        { key: "target_type", header: "Target", render: log => <span className="break-all">{log.target_type}:{log.target_id}</span> },
        { key: "created_at", header: "When", sortable: true, render: log => <div><p className="tabular-nums">{new Date(log.created_at).toLocaleString(formatLocale())}</p><p className="text-muted"><RelativeTime date={log.created_at} /></p></div> },
        { key: "details", header: "Details", render: log => <AuditLogDetails action={log.action} meta={log.meta} redacted={log.meta_redacted} /> },
      ]} /> }}
    pagination={{ page: list.page, pageSize: 24, count: logs.data?.count ?? 0, onChange: page => list.setPage(page) }} />;
}
