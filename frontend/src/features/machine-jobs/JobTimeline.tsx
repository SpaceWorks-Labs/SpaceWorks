import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { Icon } from "../../components/ui";
import { TIMELINE_STEPS, type MemberJob } from "./types";

const exact = (iso: string) => new Intl.DateTimeFormat(formatLocale(), { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
const BAD = new Set(["failed", "cancelled", "not_collected"]);

/** Every step the job has reached, oldest first, each with its exact time. */
export function JobTimeline({ timeline }: { timeline: MemberJob["timeline"] }) {
  const steps = [...timeline].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  if (!steps.length) return null;
  return <ol className="grid gap-0" aria-label={t`Job timeline`}>
    {steps.map((row, index) => {
      const last = index === steps.length - 1;
      return <li key={`${row.step}-${row.at}`} className="grid grid-cols-[1.5rem_1fr] gap-3" aria-current={last ? "step" : undefined}>
        <span className="flex flex-col items-center">
          <span className={`grid h-6 w-6 place-items-center rounded-full border ${BAD.has(row.step) ? "border-danger-line text-danger" : last ? "border-accent bg-accent-soft text-accent-ink" : "border-line text-success-ink"}`}>
            <Icon name={BAD.has(row.step) ? "CircleAlert" : "Check"} className="h-3 w-3" />
          </span>
          {!last ? <span aria-hidden="true" className="w-px flex-1 bg-line" /> : null}
        </span>
        <div className={`min-w-0 ${last ? "" : "pb-4"}`}>
          <p className={`text-sm ${last ? "font-semibold text-ink" : "text-ink"}`}>{TIMELINE_STEPS[row.step] ?? row.step.replace(/_/g, " ")}</p>
          <p className="text-xs text-muted"><time dateTime={row.at}>{exact(row.at)}</time></p>
        </div>
      </li>;
    })}
  </ol>;
}
