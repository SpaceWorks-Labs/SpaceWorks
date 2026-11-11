import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { ErrorBlock, Skeleton } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { areaKeys, areaLabel, areaPaymentsApi, owedText, type AreaGroup } from "./areaPaymentsApi";

/**
 * Decision 241/242: money waiting, one card per area, from `area-queue/summary`. Each card is a
 * filter: choosing it narrows the list below to that area (the Space Manager's combined view), and
 * choosing it again clears the filter. `pinned` shows just that area (an area console's own queue).
 */
export function AreaPaymentGroups({ makerspaceId, active, onSelect, pinned }: {
  makerspaceId: number; active: string; onSelect?: (area: string) => void; pinned?: string;
}) {
  const summary = useQuery({ queryKey: areaKeys.summary(makerspaceId), queryFn: () => areaPaymentsApi.summary(makerspaceId) });
  if (summary.isLoading) return <div role="status" aria-label={t`Loading money by area`}><Skeleton className="h-20 w-full" /></div>;
  if (summary.error) return <ErrorBlock error={summary.error} resource={t`money by area`} onRetry={() => { void summary.refetch(); }} />;
  const groups = (summary.data?.groups ?? []).filter(group => !pinned || group.area === pinned);
  if (!groups.length) return <p className="text-sm text-muted">{t`Nothing waiting to be collected.`}</p>;
  return <section aria-label={t`Money waiting by area`} className="grid gap-2">
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{groups.map(group => <li key={group.area}>
      <GroupCard group={group} selected={active === group.area}
        onClick={onSelect && !pinned ? () => onSelect(active === group.area ? "" : group.area) : undefined} />
    </li>)}</ul>
  </section>;
}

function GroupCard({ group, selected, onClick }: { group: AreaGroup; selected: boolean; onClick?: () => void }) {
  const owed = owedText(group.owed, formatMoney);
  const body = <>
    <span className="flex items-baseline justify-between gap-2">
      <span className="font-semibold text-ink">{areaLabel(group.area)}</span>
      <span className="tabular-nums text-sm text-muted">{t`${group.pending} to collect`}</span>
    </span>
    {owed ? <span className="tabular-nums font-semibold text-ink [overflow-wrap:anywhere]">{owed}</span> : null}
    <span className="flex flex-wrap gap-x-3 text-xs text-muted">
      <span className={group.overdue ? "font-semibold text-danger" : undefined}>{t`${group.overdue} overdue`}</span>
      <span>{t`${group.claims} say they paid`}</span>
    </span>
  </>;
  const frame = `grid w-full gap-1 rounded-xl border p-3 text-left ${selected ? "border-accent bg-surface" : "border-line bg-panel"}`;
  if (!onClick) return <div className={frame}>{body}</div>;
  return <button type="button" className={`${frame} min-h-11 cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus`}
    aria-pressed={selected} aria-label={t`${areaLabel(group.area)}: ${group.pending} to collect`} onClick={onClick}>{body}</button>;
}
