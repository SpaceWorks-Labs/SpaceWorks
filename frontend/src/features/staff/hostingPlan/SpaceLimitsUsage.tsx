import { t } from "@lingui/core/macro";
import { ErrorText, StatusPill } from "../../../components/ui";
import { limitHint, limitLabel, limitSource } from "../platformSpaces/limitCopy";
import { LEVEL_PILL, LimitUsage } from "../platformSpaces/LimitRowView";
import { groupLimits, type UnifiedLimit } from "../platformSpaces/limitsModel";
import { useSpaceLimitsUsage, type SpaceLimitsUsageData } from "./spacePlanApi";
import { LogoLoader } from "../../../components/LogoLoader";

/** The server's limited rows as the shared limit shape; `area` is the module group the row is shown under. */
export function usageRows(data: SpaceLimitsUsageData): UnifiedLimit[] {
  return data.rows.map(row => ({ key: row.key, label: row.label, area: row.group || "other", unit: row.unit, limit: row.limit,
    used: row.used, percent: row.percent, level: row.level, stored: undefined, source: row.source, editable: false }));
}

/**
 * The Space Manager's read-only "Limits and usage", grouped by module like the module switches (decisions 281, 284, 328a):
 * a bar from the first use, "Near limit" from 80 %, "At limit" at 100 %, and where each value comes from (platform
 * default or set for this space). Only the platform operator changes limits; reading, exporting, paying existing
 * charges and refunds are never blocked by them. Keys with no limit are not listed: they are unlimited.
 */
export function SpaceLimitsUsage({ makerspaceId }: { makerspaceId: number }) {
  const query = useSpaceLimitsUsage(makerspaceId);
  if (query.isLoading) return <LogoLoader size={48} className="min-h-32 py-3" />;
  if (query.isError || !query.data) return <ErrorText resource={t`this space's limits`} onRetry={() => { void query.refetch(); }} />;
  const groups = groupLimits(usageRows(query.data), query.data.groups);
  if (!groups.length) return <p className="text-sm text-muted">{t`No limits are set for this space: everything is unlimited.`}</p>;
  return <div className="grid gap-6">
    <p className="text-sm text-muted">{t`Set by the platform operator, for the whole platform or for this space. Every limit starts as no limit; a limit only stops something new, never reading, exporting, paying existing charges or refunds. Anything not listed is unlimited.`}</p>
    {groups.map(group => <section key={group.key} aria-labelledby={`usage-${makerspaceId}-${group.key}`} className="grid gap-1">
      <h3 id={`usage-${makerspaceId}-${group.key}`} className="title-section">{group.label}</h3>
      <ul className="grid">{group.rows.map(row => {
        const pill = row.level === "ok" ? null : LEVEL_PILL()[row.level];
        return <li key={row.key} className="grid gap-1 border-b border-line py-3 last:border-b-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{limitLabel(row.key, row.label)}</p>
            {pill ? <StatusPill label={pill.label} tone={pill.tone} /> : null}
            {row.source ? <StatusPill label={row.source === "override" ? t`Set for this space` : limitSource(row.source)} tone="neutral" /> : null}
          </div>
          <p className="text-xs text-muted">{limitHint(row.key)}</p>
          <LimitUsage row={row} />
        </li>;
      })}</ul>
    </section>)}
  </div>;
}
