import { plural } from "../../lib/plural";

type Day = { date: string; count: number };
const TONES = {
  // SpaceWorks activity and GitHub contributions are different sources, so they never share a colour.
  brand: ["bg-hover", "bg-brand/25", "bg-brand/50", "bg-brand/75", "bg-brand"],
  success: ["bg-hover", "bg-success/25", "bg-success/50", "bg-success/75", "bg-success"],
} as const;

function level(count: number, max: number) {
  if (count <= 0 || max <= 0) return 0;
  return Math.min(4, Math.ceil((count / max) * 4));
}

/** Columns are weeks, rows are weekdays (Sunday first), like a contribution calendar. */
export function weekColumns(days: Day[]) {
  const sorted = [...days].sort((left, right) => left.date.localeCompare(right.date));
  const first = sorted[0] ? new Date(`${sorted[0].date}T00:00:00`).getDay() : 0;
  const cells: (Day | null)[] = [...Array<null>(Number.isNaN(first) ? 0 : first).fill(null), ...sorted];
  const columns: (Day | null)[][] = [];
  for (let index = 0; index < cells.length; index += 7) columns.push(cells.slice(index, index + 7));
  return columns;
}

/**
 * Counts only: the graph shows how much happened on a day, never what. The summary is the
 * accessible name; the cells are decorative with a hover title for pointer users.
 */
export function ContributionGrid({ title, days, tone, unit }: {
  title: string; days: Day[]; tone: keyof typeof TONES; unit: [string, string];
}) {
  const total = days.reduce((sum, row) => sum + Math.max(0, row.count), 0);
  const max = days.reduce((highest, row) => Math.max(highest, row.count), 0);
  const summary = `${plural(total, unit[0], unit[1])} in the past ${days.length} days`;
  return <section aria-label={title} className="grid gap-3">
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h3 className="title-section">{title}</h3>
      <p className="text-sm text-muted tabular-nums">{summary}</p>
    </div>
    <div role="img" aria-label={`${title}: ${summary}`} className="flex gap-1 overflow-x-auto pb-1">
      {weekColumns(days).map((column, index) => <div key={index} className="grid shrink-0 grid-rows-7 gap-1">
        {column.map((cell, row) => <span key={row} aria-hidden="true"
          title={cell ? `${cell.date}: ${cell.count}` : undefined}
          className={`block h-3.5 w-3.5 rounded-[3px] ${cell ? TONES[tone][level(cell.count, max)] : "bg-transparent"}`} />)}
      </div>)}
    </div>
  </section>;
}
