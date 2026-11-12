import { t } from "@lingui/core/macro";
import type { ReportCatalogItem } from "./operationsReportsConfig";
import { groupChoices, hubEmptyReason } from "./reportGroups";

/** Search plus one chip per module group; the chips are how the "Reports" link inside a module area lands on its group. */
export function ReportHubFilters({ reports, visibleCount, reportsEnabled, loading = false, query, group, onQuery, onGroup }: {
  reports: ReportCatalogItem[]; visibleCount: number; reportsEnabled: boolean; loading?: boolean; query: string; group: string;
  onQuery: (value: string) => void; onGroup: (value: string) => void;
}) {
  const choices = groupChoices(reports);
  const reason = loading ? null : hubEmptyReason({ reportsEnabled, catalogCount: reports.length, visibleCount });
  return <section aria-label={t`Find a report`} className="mb-5 grid gap-3">
    <label className="grid gap-1 text-sm">{t`Search reports`}
      <input type="search" className="desk-input w-full" value={query} placeholder={t`Name, module or topic`}
        onChange={event => onQuery(event.target.value)} /></label>
    {choices.length > 1 ? <div role="group" aria-label={t`Module`} className="flex flex-wrap gap-2">
      <button type="button" aria-pressed={!group} className="desk-button min-h-11" onClick={() => onGroup("")}>{t`All modules`}</button>
      {choices.map(choice => <button key={choice.key} type="button" aria-pressed={group === choice.key} className="desk-button min-h-11"
        onClick={() => onGroup(group === choice.key ? "" : choice.key)}>{choice.label} ({choice.count})</button>)}
    </div> : null}
    {reason === "module_off" ? <p role="status" className="text-sm text-muted">{t`Reports are switched off for this makerspace, so no report is listed. A space manager can turn them on under Modules.`}</p> : null}
    {reason === "no_match" ? <p role="status" className="text-sm text-muted">{t`No report matches this search. Clear the search or choose All modules.`}</p> : null}
  </section>;
}
