import { formatDateTime } from "../../lib/format";
import { plural, t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, Pagination, StatusPill, type Tone } from "../../components/ui";
import { categoryLabel, channelLabel } from "./channelCatalog";
import { useDeliveries, type Delivery } from "./channelsApi";
import { notificationEventLabel } from "./notificationEventLabels";
import { LogoLoader } from "../../components/LogoLoader";

const STATE_TONES: Record<Delivery["state"], Tone> = { accepted: "info", sent: "success", delivered: "success", read: "success",
  held: "warn", retrying: "warn", failed: "danger", skipped: "neutral" };
const stateLabel = (state: string) => ({ accepted: t`Accepted`, sent: t`Sent`, delivered: t`Delivered`, read: t`Read`,
  held: t`Held`, retrying: t`Retrying`, failed: t`Failed`, skipped: t`Skipped` } as Record<string, string>)[state] ?? t`Unknown`;

/**
 * Delivery metadata only (channel, state, attempts, a sanitized error) — never a body or a
 * destination. A Space Manager sees the whole space; everyone else sees their own.
 */
export function ChannelDeliveryLog({ makerspaceId, member = false, title = t`Delivery log` }: {
  makerspaceId: number; member?: boolean; title?: string;
}) {
  const [page, setPage] = useState(1);
  const deliveries = useDeliveries(makerspaceId, page, member);
  const rows = deliveries.error ? [] : deliveries.data?.results ?? [];
  return <section aria-label={title} className="grid min-w-0 gap-3">
    <h3 className="title-section">{title}</h3>
    {deliveries.isLoading ? <LogoLoader label={t`Loading deliveries…`} size={48} className="min-h-16 py-3" /> : null}
    {deliveries.error ? <ErrorBlock error={deliveries.error} onRetry={() => { void deliveries.refetch(); }} /> : null}
    {!deliveries.error && deliveries.data && !rows.length ? <p className="text-sm text-muted">{t`Nothing has been sent through these channels yet.`}</p> : null}
    {rows.length ? <ul className="grid min-w-0 divide-y divide-line rounded-lg border border-line">
      {rows.map(row => <li key={row.id} className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
        <StatusPill label={stateLabel(row.state)} tone={STATE_TONES[row.state] ?? "neutral"} />
        <span className="font-semibold text-ink">{channelLabel(row.channel)}</span>
        <span className="min-w-0 flex-1 break-words text-muted">{categoryLabel(row.feature)} · {notificationEventLabel(row.event)}</span>
        <time className="text-muted tabular-nums" dateTime={row.created_at}>{formatDateTime(row.created_at)}</time>
        {row.attempt_count > 1 || row.last_error ? <span className="w-full text-xs text-muted">
          {plural(row.attempt_count, { one: "# attempt", other: "# attempts" })}{row.last_error ? ` · ${row.last_error}` : ""}
          {row.next_attempt_at ? t` · next try ${formatDateTime(row.next_attempt_at)}` : ""}</span> : null}
      </li>)}
    </ul> : null}
    {!deliveries.error && deliveries.data ? <Pagination page={page} pageSize={24} count={deliveries.data.count}
      totalPages={Math.max(1, Math.ceil(deliveries.data.count / 24))} onChange={setPage} /> : null}
  </section>;
}
