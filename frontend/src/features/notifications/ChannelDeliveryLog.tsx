import { useState } from "react";

import { ErrorBlock, Pagination, StatusPill, type Tone } from "../../components/ui";
import { CATEGORY_LABELS, CHANNEL_LABELS } from "./channelCatalog";
import { useDeliveries, type Delivery } from "./channelsApi";

const STATE_TONES: Record<Delivery["state"], Tone> = { accepted: "info", sent: "success", delivered: "success", read: "success",
  held: "warn", retrying: "warn", failed: "danger", skipped: "neutral" };
const label = (value: string) => value.replace(/_/g, " ");

/**
 * Delivery metadata only (channel, state, attempts, a sanitized error) — never a body or a
 * destination. A Space Manager sees the whole space; everyone else sees their own.
 */
export function ChannelDeliveryLog({ makerspaceId, member = false, title = "Delivery log" }: {
  makerspaceId: number; member?: boolean; title?: string;
}) {
  const [page, setPage] = useState(1);
  const deliveries = useDeliveries(makerspaceId, page, member);
  const rows = deliveries.error ? [] : deliveries.data?.results ?? [];
  return <section aria-label={title} className="grid min-w-0 gap-3">
    <h3 className="title-section">{title}</h3>
    {deliveries.isLoading ? <p className="text-sm text-muted">Loading deliveries…</p> : null}
    {deliveries.error ? <ErrorBlock error={deliveries.error} onRetry={() => { void deliveries.refetch(); }} /> : null}
    {!deliveries.error && deliveries.data && !rows.length ? <p className="text-sm text-muted">Nothing has been sent through these channels yet.</p> : null}
    {rows.length ? <ul className="grid min-w-0 divide-y divide-line rounded-lg border border-line">
      {rows.map(row => <li key={row.id} className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
        <StatusPill label={label(row.state)} tone={STATE_TONES[row.state] ?? "neutral"} />
        <span className="font-semibold text-ink">{CHANNEL_LABELS[row.channel] ?? label(row.channel)}</span>
        <span className="min-w-0 flex-1 break-words text-muted">{CATEGORY_LABELS[row.feature] ?? label(row.feature)} · {label(row.event)}</span>
        <time className="text-muted tabular-nums" dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time>
        {row.attempt_count > 1 || row.last_error ? <span className="w-full text-xs text-muted">
          {row.attempt_count} attempt{row.attempt_count === 1 ? "" : "s"}{row.last_error ? ` · ${row.last_error}` : ""}
          {row.next_attempt_at ? ` · next try ${new Date(row.next_attempt_at).toLocaleString()}` : ""}</span> : null}
      </li>)}
    </ul> : null}
    {!deliveries.error && deliveries.data ? <Pagination page={page} pageSize={24} count={deliveries.data.count}
      totalPages={Math.max(1, Math.ceil(deliveries.data.count / 24))} onChange={setPage} /> : null}
  </section>;
}
