import { t } from "@lingui/core/macro";
import { Field } from "../../../components/ui";
import type { ReportCatalogItem } from "./operationsReportsConfig";
import { ReportPinButton } from "./ReportPinButton";
import { groupReports } from "./reportGroups";

/** A report whose source module or capability is off is hidden, never listed as disabled (#183B). */
export const liveReports = (reports: ReportCatalogItem[]) => reports.filter(report => report.available !== false);

type Pins = { pinned?: ReadonlySet<string>; onTogglePin?: (key: string) => void };
const NONE: ReadonlySet<string> = new Set();

/** Below xl the layout stacks the aside AFTER the report, so the picker leads the main column instead. */
export function OperationsReportPicker({ reports, selected, onSelect, pinned = NONE }: {
  reports: ReportCatalogItem[]; selected: string; onSelect: (key: string) => void; pinned?: ReadonlySet<string>;
}) {
  return <div className="mb-5 xl:hidden"><Field label={t`Report`}><select className="desk-input w-full" value={selected} onChange={event => onSelect(event.target.value)}>
    {groupReports(liveReports(reports), pinned, t`Pinned`).map(group => <optgroup key={group.key} label={group.label}>{group.reports.map(report =>
      <option key={report.key} value={report.key}>{report.title}</option>)}</optgroup>)}
  </select></Field></div>;
}

export function OperationsReportNavigation({ reports, selected, onSelect, pinned = NONE, onTogglePin }: {
  reports: ReportCatalogItem[]; selected: string; onSelect: (key: string) => void;
} & Pins) {
  return <nav aria-label={t`Reports`} className="hidden min-w-0 xl:block">
    <div className="space-y-5">{groupReports(liveReports(reports), pinned, t`Pinned`).map(group => <section key={group.key}>
      <h2 className="eyebrow mb-2">{group.label}</h2>
      <div className="grid gap-1">{group.reports.map(report => <div key={report.key} className="flex items-center">
        <button type="button" aria-current={selected === report.key ? "page" : undefined} onClick={() => onSelect(report.key)}
          className={`min-h-11 min-w-0 flex-1 rounded-control border px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${selected === report.key ? "border-accent bg-accent-soft text-accent-ink" : "border-transparent text-ink hover:bg-hover"}`}>
          {report.title}
        </button>
        {onTogglePin ? <ReportPinButton title={report.title} pinned={pinned.has(report.key)} onToggle={() => onTogglePin(report.key)} /> : null}
      </div>)}</div>
    </section>)}</div>
  </nav>;
}
