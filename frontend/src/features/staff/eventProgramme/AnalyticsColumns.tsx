import { plural, t } from "@lingui/core/macro";
import { formatLocale } from "../../../lib/format";

type Column = { key: string; label: string; count: number };

/**
 * A column chart for counts over time (B24): one bar per day or arrival window in the brand colour, a light
 * baseline, the peak value labelled, and every number repeated in a visually hidden table for screen readers.
 */
export function ColumnChart({ title, columns, summary, empty }: { title: string; columns: Column[]; summary: string; empty: string }) {
  const max = Math.max(1, ...columns.map(column => column.count));
  const peak = columns.reduce<Column | null>((best, column) => !best || column.count > best.count ? column : best, null);
  const sparse = columns.length > 14;
  return <figure className="grid min-w-0 gap-2">
    <figcaption className="font-semibold">{title}</figcaption>
    {columns.length ? <>
      <div aria-hidden="true" className="flex h-36 items-end gap-[2px] border-b border-line">
        {columns.map(column => <div key={column.key} className="group relative flex h-full min-w-0 flex-1 flex-col justify-end" title={`${column.label}: ${column.count}`}>
          {column === peak ? <span className="absolute inset-x-0 top-0 text-center text-xs font-semibold tabular-nums text-ink">{column.count}</span> : null}
          <span className="block rounded-t-sm bg-brand transition-opacity group-hover:opacity-80 motion-reduce:transition-none"
            style={{ height: `${Math.max(column.count ? 3 : 0, (column.count / max) * 88)}%` }} />
        </div>)}
      </div>
      <div aria-hidden="true" className="flex justify-between gap-2 text-xs tabular-nums text-muted">
        <span>{columns[0].label}</span>{sparse || columns.length < 2 ? null : <span>{columns[Math.floor(columns.length / 2)].label}</span>}<span>{columns[columns.length - 1].label}</span>
      </div>
      <table className="sr-only"><caption>{title}</caption><tbody>{columns.map(column => <tr key={column.key}><th scope="row">{column.label}</th><td>{column.count}</td></tr>)}</tbody></table>
    </> : null}
    <p className="text-xs text-muted">{columns.length ? summary : empty}</p>
  </figure>;
}

/** "15-minute" or "2-hour": the arrival window the server picked for how spread out check-ins were. */
export function windowLabel(minutes: number) {
  if (minutes < 60 || minutes % 60) return plural(minutes, { one: "#-minute", other: "#-minute" });
  return plural(minutes / 60, { one: "#-hour", other: "#-hour" });
}

export const dayLabel = (day: string) => new Date(`${day}T12:00:00`).toLocaleDateString(formatLocale(), { day: "numeric", month: "short" });

/** How many people wrote something for each written feedback question; the text itself is never shown here. */
export function WrittenAnswers({ rows }: { rows: { question_id: string; label: string; answered: number }[] }) {
  if (!rows.length) return null;
  return <section className="grid gap-2" aria-label={t`Written answers`}>
    <h5 className="font-semibold">{t`Written answers`}</h5>
    <ul className="grid gap-1 text-sm">{rows.map(row => <li key={row.question_id} className="flex flex-wrap justify-between gap-2 border-b border-line py-1.5">
      <span className="min-w-0 [overflow-wrap:anywhere]">{row.label || t`Feedback question`}</span>
      <span className="tabular-nums text-muted">{plural(row.answered, { one: "# person wrote an answer", other: "# people wrote an answer" })}</span>
    </li>)}</ul>
    <p className="text-xs text-muted">{t`Read the answers themselves in Feedback; only counts are shown here.`}</p>
  </section>;
}
