import { Field } from "../../../components/ui";
import type { ReportCatalogItem } from "./operationsReportsConfig";

import { reportAreaGroups as grouped } from "./reportAreas";

/** Below xl the layout stacks the aside AFTER the report, so the picker leads the main column instead. */
export function OperationsReportPicker({ reports, selected, onSelect }: {
  reports: ReportCatalogItem[]; selected: string; onSelect: (key: string) => void;
}) {
  return <div className="mb-5 xl:hidden"><Field label="Report"><select className="desk-input w-full" value={selected} onChange={event => onSelect(event.target.value)}>
    {[...grouped(reports)].map(([group, entries]) => <optgroup key={group} label={group}>{entries.map(report =>
      <option key={report.key} value={report.key} disabled={report.available === false}>{report.title}</option>)}</optgroup>)}
  </select></Field></div>;
}

export function OperationsReportNavigation({ reports, selected, onSelect }: {
  reports: ReportCatalogItem[]; selected: string; onSelect: (key: string) => void;
}) {
  return <nav aria-label="Reports" className="hidden min-w-0 xl:block">
    <div className="space-y-5">{[...grouped(reports)].map(([group, entries]) => <section key={group}>
      <h2 className="eyebrow mb-2">{group}</h2>
      <div className="grid gap-1">{entries.map(report => <button key={report.key} type="button"
        aria-current={selected === report.key ? "page" : undefined} disabled={report.available === false}
        title={report.unavailable_reason ?? undefined} onClick={() => onSelect(report.key)}
        className={`min-h-11 rounded-control border px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${selected === report.key ? "border-accent bg-accent-soft text-accent-ink" : "border-transparent text-ink hover:bg-hover disabled:text-muted"}`}>
        {report.title}{report.available === false ? <span className="mt-1 block text-xs text-muted">{report.unavailable_reason ?? "Unavailable in this makerspace"}</span> : null}
      </button>)}</div>
    </section>)}</div>
  </nav>;
}
