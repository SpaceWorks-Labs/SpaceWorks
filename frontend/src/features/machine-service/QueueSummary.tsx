import { plural, t } from "@lingui/core/macro";
import { StatusPill } from "../../components/ui";
import { clockLabel, minutesLabel } from "./ServiceRequestEta";
import type { MachineQueueSummary } from "./types";

/** A machine's simulated final free-at time, from the server's summary. Unknown never reads as zero. */
export function QueueSummary({ summary, now }: { summary: MachineQueueSummary | null | undefined; now?: Date }) {
  if (!summary) return null;
  const jobs = plural(summary.length, { one: "# job in line", other: "# jobs in line" });
  if (summary.confidence === "unavailable" || summary.eta_minutes == null || !summary.estimated_clear_at) {
    return <span className="inline-flex flex-wrap items-center gap-2 text-sm text-muted"><StatusPill label={t`Clear time unavailable`} tone="neutral" />{summary.length ? jobs : null}</span>;
  }
  const when = summary.eta_minutes <= 0 ? t`Free now`
    : <>{t`Estimated queue clears in ${minutesLabel(summary.eta_minutes)} (around `}<time dateTime={summary.estimated_clear_at}>{clockLabel(summary.estimated_clear_at, now ?? new Date())}</time>)</>;
  return <span className="inline-flex flex-wrap items-center gap-2 text-sm text-ink">
    <span>{when}</span>{summary.confidence === "rough" ? <StatusPill label={t`Rough estimate`} tone="warn" /> : null}
    {summary.length ? <span className="text-muted">{jobs}</span> : null}
  </span>;
}
