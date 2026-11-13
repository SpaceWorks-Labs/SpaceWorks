import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { StatusPill } from "../../components/ui";
import type { UsageSample } from "./types";

function valid(value: number | null): value is number {
  return value !== null && Number.isFinite(value) && value >= 0;
}
export function formatUsage(value: number | null, unit: UsageSample["unit"]) {
  if (!valid(value)) return t`Unknown`;
  if (unit === "recipients") return t`${value.toLocaleString(formatLocale())} recipients`;
  return t`${(value / 1_000_000).toLocaleString(formatLocale(), { maximumFractionDigits: 1 })} MB`;
}
type QuotaLevel = "unknown" | "stale" | "reached" | "near" | "watch" | "within";
function quotaLevel(sample: UsageSample): QuotaLevel {
  if (!valid(sample.used) || !valid(sample.cap) || sample.cap === 0 || !sample.sampled_at
    || !Number.isFinite(Date.parse(sample.sampled_at))) return "unknown";
  if (sample.state === "unknown") return "unknown";
  if (sample.state === "stale") return "stale";
  const ratio = (sample.used + (valid(sample.uncertain) ? sample.uncertain : 0)) / sample.cap;
  return ratio >= 1 ? "reached" : ratio >= 0.9 ? "near" : ratio >= 0.7 ? "watch" : "within";
}
/** The translated state label for a usage sample. */
export function quotaState(sample: UsageSample) {
  switch (quotaLevel(sample)) {
    case "unknown": return t`Unknown`;
    case "stale": return t`Stale`;
    case "reached": return t`Reached`;
    case "near": return t`Near limit`;
    case "watch": return t`Watch usage`;
    default: return t`Within configured cap`;
  }
}
export function QuotaCard({ label, sample }: { label: string; sample: UsageSample }) {
  const level = quotaLevel(sample);
  const state = quotaState(sample);
  const unknown = t`Unknown`;
  const warning = level !== "within";
  return <section className="min-w-0 rounded-xl border border-line bg-panel p-4" aria-label={label}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold text-ink">{label}</h3>
      <StatusPill tone={level === "reached" ? "danger" : warning ? "warn" : "neutral"} label={state} />
    </div>
    <p className="mt-3 text-ink">{formatUsage(sample.used, sample.unit)} / {formatUsage(sample.cap, sample.unit)}</p>
    <p className="mt-1 text-sm text-muted">{t`Uncertain or reserved: ${formatUsage(sample.uncertain, sample.unit)}. Included when evaluating the cap.`}</p>
    <p className="mt-2 text-xs text-muted">{t`Usage source: ${sample.source || unknown}. Cap source: ${sample.cap_source || unknown}. Cap checked: ${dateLabel(sample.cap_verified_on)}. Sampled: ${dateLabel(sample.sampled_at)}.`}</p>
    {warning ? <p className="mt-2 text-sm text-ink">{level === "unknown" || level === "stale"
      ? t`Ask the operator to refresh usage and verify the provider account allowance.`
      : t`Review the provider account and pending work. Export, migrate or upgrade before reaching the limit; retain immutable history.`}</p> : null}
  </section>;
}
export function dateLabel(value: string | null) {
  return value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString(formatLocale()) : t`Unknown`;
}
