import { formatDateTime } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { EmptyState, ListRow, StatusBadge } from "../../components/ui";
import type { EventHistory, HistoryEvent } from "./eventHistoryApi";

function statusLabel(status: string) {
  switch (status) {
    case "registered": return t`Registered`;
    case "attended": return t`Attended`;
    case "waitlisted": return t`Waitlisted`;
    case "pending_approval": return t`Pending approval`;
    case "rejected": return t`Rejected`;
    case "cancelled": return t`Cancelled`;
    default: return t`Status unknown`;
  }
}
const when = (event: HistoryEvent) => `${formatDateTime(event.starts_at)}${event.location ? ` · ${event.location}` : ""}`;

/** Counts plus the registrations and talks behind them; shared by the member area and the staff member drawer. */
export function EventHistoryLists({ history, emptyMessage, compact = false }: { history: EventHistory; emptyMessage: string; compact?: boolean }) {
  // Tolerate a partial body rather than crash the drawer or page that hosts this block.
  const registrations = Array.isArray(history.registrations) ? history.registrations : [];
  const speaking = Array.isArray(history.speaking) ? history.speaking : [];
  const counts = history.counts ?? { registered: 0, attended: 0, cancelled: 0, speaking: 0 };
  if (!registrations.length && !speaking.length) return <EmptyState message={emptyMessage} />;
  const stats = [["Registered", counts.registered], ["Attended", counts.attended], ["Cancelled", counts.cancelled], ["Speaking", counts.speaking]] as const;
  const shown = compact ? 5 : registrations.length;
  return <div className="grid gap-5">
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">{stats.map(([label, value]) => <div key={label} className="min-w-0 rounded-xl border border-line bg-panel p-3">
      <dt className="text-sm text-muted">{label}</dt><dd className="mt-1 text-xl font-semibold tabular-nums text-ink">{value}</dd></div>)}</dl>
    {speaking.length ? <section className="grid gap-3" aria-label={t`Spoke at`}>
      <h3 className="title-section">{t`Spoke at`}</h3>
      {speaking.slice(0, compact ? 5 : undefined).map((row) => <ListRow key={row.speaker_id} title={row.event.title}
        identity={{ kind: "date", date: row.event.starts_at }} meta={when(row.event)} right={<StatusBadge status="speaker" label={t`Speaker`} />} />)}
    </section> : null}
    {registrations.length ? <section className="grid gap-3" aria-label={t`Registrations`}>
      <h3 className="title-section">{compact ? t`Recent registrations` : t`Registrations`}</h3>
      {registrations.slice(0, shown).map((row) => <ListRow key={row.registration_id} title={row.event.title}
        identity={{ kind: "date", date: row.event.starts_at }} meta={when(row.event)}
        right={<StatusBadge status={row.status} label={statusLabel(row.status)} />} />)}
      {compact && registrations.length > shown ? <p className="text-sm text-muted">{t`Showing the ${shown} most recent of ${registrations.length}.`}</p> : null}
    </section> : null}
  </div>;
}
