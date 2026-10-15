import { Field } from "../../../components/ui";
import type { ReportCatalogItem } from "./operationsReportsConfig";

const groupFor = (key: string) => {
  if (/loan|lent|borrow|return|taken|summary/.test(key)) return "Lending";
  if (/invent|procure|damaged|lost|added|import|evidence|qr/.test(key)) return "Inventory";
  if (/machine|printer|booking|maintenance|certification|fablab/.test(key)) return "Machines";
  if (/payment|revenue|financ|income/.test(key)) return "Money";
  if (/member|event|community/.test(key)) return "Community";
  return "System";
};

export function OperationsReportNavigation({ reports, selected, onSelect }: {
  reports: ReportCatalogItem[]; selected: string; onSelect: (key: string) => void;
}) {
  const groups = new Map<string, ReportCatalogItem[]>();
  for (const report of reports) { const group = groupFor(report.key); groups.set(group, [...(groups.get(group) ?? []), report]); }
  return <nav aria-label="Reports" className="min-w-0">
    <div className="md:hidden"><Field label="Report"><select className="desk-input" value={selected} onChange={event => onSelect(event.target.value)}>
      {[...groups].map(([group, entries]) => <optgroup key={group} label={group}>{entries.map(report =>
        <option key={report.key} value={report.key} disabled={report.available === false}>{report.title}</option>)}</optgroup>)}
    </select></Field></div>
    <div className="hidden space-y-5 md:block">{[...groups].map(([group, entries]) => <section key={group}>
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
