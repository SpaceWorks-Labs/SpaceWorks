import { identityTone, toneClasses } from "./tones";
import type { Tone } from "./types";
export type DateChipProps = { date: string; seed?: string; tone?: Tone; draft?: boolean };
export function DateChip({ date, seed = date, tone, draft }: DateChipProps) {
  // Date-only values are calendar dates, not UTC instants that can shift a day.
  const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(date) ? `${date}T12:00:00` : date);
  if (Number.isNaN(parsed.getTime())) return <span className="text-sm text-muted">Unknown date</span>;
  return <time dateTime={date} aria-label={parsed.toLocaleDateString("en", { dateStyle: "long" })}
    className="inline-flex h-13 w-13 shrink-0 flex-col overflow-hidden rounded-md border border-line bg-panel text-center">
    <span className={`border px-1 text-xs font-semibold uppercase ${toneClasses[draft ? "neutral" : tone ?? identityTone(seed)]}`}>
      {parsed.toLocaleDateString("en", { month: "short" })}</span>
    <span className="flex flex-1 items-center justify-center font-display text-xl font-extrabold text-ink">{parsed.getDate()}</span>
  </time>;
}
