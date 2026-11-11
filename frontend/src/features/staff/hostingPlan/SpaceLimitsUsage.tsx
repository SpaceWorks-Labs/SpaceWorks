import { t } from "@lingui/core/macro";
import { ErrorText, Skeleton, StatusPill } from "../../../components/ui";
import { limitHint, limitLabel } from "../platformSpaces/limitCopy";
import { LEVEL_PILL, LimitUsage } from "../platformSpaces/LimitRowView";
import { groupLimits, levelOf, percentOf, type UnifiedLimit } from "../platformSpaces/limitsModel";
import { useSpacePlanUsage, type SpacePlanUsage, type UsageRow } from "./spacePlanApi";

/** Every usage row the server sends, one per key: the space's quotas and platform use first, then the plan's. */
export function usageRows(data: SpacePlanUsage): UnifiedLimit[] {
  const seen = new Set<string>();
  const rows: UsageRow[] = [...(data.space_quota_resources ?? []), ...(data.platform_resources ?? []), ...(data.resources ?? [])];
  return rows.filter(row => !seen.has(row.key) && Boolean(seen.add(row.key))).map(row => {
    const percent = row.percent ?? percentOf(row.used, row.limit);
    return { key: row.key, label: row.label, area: row.area || "other", unit: row.unit, limit: row.limit, used: row.used,
      percent, level: row.level ?? levelOf(percent), stored: undefined, editable: false };
  });
}

/**
 * The Space Manager's read-only view of every limit on this space, grouped by area (decisions 281, 284):
 * a bar from the first use, "Near limit" from 80 %, "At limit" at 100 %. Only the platform operator
 * changes limits; reading, exporting, paying existing charges and refunds are never blocked by them.
 */
export function SpaceLimitsUsage({ makerspaceId }: { makerspaceId: number }) {
  const query = useSpacePlanUsage(makerspaceId, true);
  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError || !query.data) return <ErrorText resource={t`this space's limits`} onRetry={() => { void query.refetch(); }} />;
  const groups = groupLimits(usageRows(query.data), undefined);
  if (!groups.length) return <p className="text-sm text-muted">{t`No limits are set for this space.`}</p>;
  return <div className="grid gap-6">
    <p className="text-sm text-muted">{t`Set by the platform operator. Every limit starts as no limit; a limit only stops something new, never reading, exporting, paying existing charges or refunds.`}</p>
    {groups.map(group => <section key={group.key} aria-labelledby={`usage-${makerspaceId}-${group.key}`} className="grid gap-1">
      <h3 id={`usage-${makerspaceId}-${group.key}`} className="title-section">{group.label}</h3>
      <ul className="grid">{group.rows.map(row => {
        const pill = row.level === "ok" ? null : LEVEL_PILL()[row.level];
        return <li key={row.key} className="grid gap-1 border-b border-line py-3 last:border-b-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{limitLabel(row.key, row.label)}</p>
            {pill ? <StatusPill label={pill.label} tone={pill.tone} /> : null}
          </div>
          <p className="text-xs text-muted">{limitHint(row.key)}</p>
          <LimitUsage row={row} />
        </li>;
      })}</ul>
    </section>)}
  </div>;
}
