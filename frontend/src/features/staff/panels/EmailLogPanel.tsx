import { ListLayout } from "../../../components/layouts";
import { ErrorBlock, ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { useUrlListState } from "../../../lib/useUrlListState";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useStaffGet, type Makerspace } from "./shared";
import { staffRequest } from "../../../lib/api";
type EmailLogStatus = "" | "sent" | "failed" | "pending" | "sending" | "skipped";
type EmailLogEntry = {
  id: number;
  to_email: string;
  subject: string;
  stream: string;
  event: string;
  audience: string;
  status: Exclude<EmailLogStatus, "">;
  error: string;
  attempts: number;
  created_at: string;
  sent_at: string | null;
};
type EmailLogResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: EmailLogEntry[];
};

export function EmailLogPanel({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const list = useUrlListState({ status: "", recent_days: "", page: "1" });
  const status = list.values.status as EmailLogStatus;
  const page = list.page;
  const setPage = list.setPage;
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (list.values.recent_days) params.set("recent_days", list.values.recent_days);
  params.set("page", String(page));
  const query = params.toString();
  const logs = useStaffGet<EmailLogResponse>(
    ["email-logs", makerspace.id, query],
    `/admin/makerspace/${makerspace.id}/email-logs?${query}`,
  );
  const retry = useMutation({
    mutationFn: (id: number) =>
      staffRequest<EmailLogEntry>(`/admin/makerspace/${makerspace.id}/email-logs/${id}/retry`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["email-logs", makerspace.id] });
    },
  });
  const updateStatus = (value: EmailLogStatus) => {
    list.setFilter("status", value);
  };
  return <ListLayout header={{ title: "Email log", subtitle: "See what reached people and retry deliveries that need attention." }}
    state={{ status: logs.isLoading ? "loading" : logs.error ? "error" : "ready", error: "Couldn't load email logs. Try again.", onRetry: () => { void logs.refetch(); } }}
    isEmpty={logs.data?.results.length === 0} filtered={Boolean(status || list.values.recent_days)}
    empty={{ message: "No email logs yet. Sent emails will appear here." }}
    filteredEmpty={{ message: "No email logs match. Try another status or date range." }}
    filters={{ controls: <div className="grid gap-3">
      {list.values.recent_days ? <button className="desk-button" onClick={() => list.setFilter("recent_days", "")}>Show all dates (currently last {list.values.recent_days} days)</button> : null}
      <select aria-label="Email log status" className="desk-input w-full" value={status} onChange={event => updateStatus(event.target.value as EmailLogStatus)}>
        <option value="">All</option>{["sent", "failed", "pending", "sending", "skipped"].map(value => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}
      </select></div> }}
    body={{ kind: "rows", rows: <>{retry.error ? <ErrorBlock error={retry.error} /> : null}{logs.data?.results.map(log => <ListRow key={log.id}
      title={log.subject || log.event || "Email"} identity={{ kind: "date", date: log.created_at }}
      meta={<span className="grid gap-1"><span className="[overflow-wrap:anywhere]">{log.to_email} · {log.event || "email"} · {log.stream || "general"}</span>
        <RelativeTime date={log.created_at} />{log.status === "failed" || log.status === "skipped" ? <span>{truncate(log.error)}</span> : null}</span>}
      right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={log.status} tone={log.status === "failed" ? "danger" : log.status === "sent" ? "success" : "neutral"} />
        {log.status === "failed" || log.status === "sending" ? <button className="desk-button" disabled={retry.isPending} onClick={() => retry.mutate(log.id)}>Retry</button> : null}</div>} />)}</> }}
    pagination={{ page, pageSize: 24, count: logs.data?.count ?? 0, onChange: setPage }} />;
}

function truncate(value: string) { return value.length > 140 ? `${value.slice(0, 137)}…` : value; }
