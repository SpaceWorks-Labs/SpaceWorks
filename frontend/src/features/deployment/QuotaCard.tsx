import { StatusPill } from "../../components/ui";
import type { UsageSample } from "./types";

function valid(value: number | null): value is number {
  return value !== null && Number.isFinite(value) && value >= 0;
}
export function formatUsage(value: number | null, unit: UsageSample["unit"]) {
  if (!valid(value)) return "Unknown";
  if (unit === "recipients") return `${value.toLocaleString()} recipients`;
  return `${(value / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })} MB`;
}
export function quotaState(sample: UsageSample) {
  if (!valid(sample.used) || !valid(sample.cap) || sample.cap === 0 || !sample.sampled_at
    || !Number.isFinite(Date.parse(sample.sampled_at))) return "Unknown";
  if (sample.state === "unknown") return "Unknown";
  if (sample.state === "stale") return "Stale";
  const ratio = (sample.used + (valid(sample.uncertain) ? sample.uncertain : 0)) / sample.cap;
  return ratio >= 1 ? "Reached" : ratio >= 0.9 ? "Near limit" : ratio >= 0.7 ? "Watch usage" : "Within configured cap";
}
export function QuotaCard({ label, sample }: { label: string; sample: UsageSample }) {
  const state = quotaState(sample);
  const warning = ["Watch usage", "Near limit", "Reached", "Unknown", "Stale"].includes(state);
  return <section className="min-w-0 rounded-xl border border-line bg-panel p-4" aria-label={label}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold text-ink">{label}</h3>
      <StatusPill tone={state === "Reached" ? "danger" : warning ? "warn" : "neutral"} label={state} />
    </div>
    <p className="mt-3 text-ink">{formatUsage(sample.used, sample.unit)} / {formatUsage(sample.cap, sample.unit)}</p>
    <p className="mt-1 text-sm text-muted">Uncertain or reserved: {formatUsage(sample.uncertain, sample.unit)}. Included when evaluating the cap.</p>
    <p className="mt-2 text-xs text-muted">Usage source: {sample.source || "Unknown"}. Cap source: {sample.cap_source || "Unknown"}. Cap checked: {dateLabel(sample.cap_verified_on)}. Sampled: {dateLabel(sample.sampled_at)}.</p>
    {warning ? <p className="mt-2 text-sm text-ink">{state === "Unknown" || state === "Stale"
      ? "Ask the operator to refresh usage and verify the provider account allowance."
      : "Review the provider account and pending work. Export, migrate or upgrade before reaching the limit; retain immutable history."}</p> : null}
  </section>;
}
export function dateLabel(value: string | null) {
  return value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : "Unknown";
}
