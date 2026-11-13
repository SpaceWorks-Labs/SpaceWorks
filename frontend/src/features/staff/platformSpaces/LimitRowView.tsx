import { t } from "@lingui/core/macro";
import { ProgressBar, StatusPill } from "../../../components/ui";
import { formatLocale } from "../../../lib/format";
import { limitHint, limitLabel, limitSource } from "./limitCopy";
import { toInput, type UnifiedLimit } from "./limitsModel";

/** A limit or usage value as people read it: KB/MB/GB for bytes, "N a minute" for a rate, grouped digits otherwise. */
export function limitAmount(row: Pick<UnifiedLimit, "unit">, value: number | null): string {
  if (value === null) return t`No limit`;
  const digits = (n: number) => n.toLocaleString(formatLocale(), { maximumFractionDigits: 1 });
  if (row.unit === "per_minute") return t`${digits(value)} a minute`;
  if (row.unit !== "bytes") return digits(value);
  if (value >= 1024 ** 3) return `${digits(value / 1024 ** 3)} GB`;
  if (value >= 1024 ** 2) return `${digits(value / 1024 ** 2)} MB`;
  return `${digits(value / 1024)} KB`;
}

export const LEVEL_PILL = (): Record<"warning" | "limit", { label: string; tone: "warn" | "danger" }> => ({
  warning: { label: t`Near limit`, tone: "warn" }, limit: { label: t`At limit`, tone: "danger" },
});

/** Usage against the limit in words, then a bar whenever there is a limit to measure against. */
export function LimitUsage({ row, showSource = false }: { row: UnifiedLimit; showSource?: boolean }) {
  const label = limitLabel(row.key, row.label);
  const source = showSource && row.source ? ` (${limitSource(row.source)})` : "";
  const text = row.used === null ? (row.limit === null ? t`No limit` : t`Limit: ${limitAmount(row, row.limit)}`)
    : row.limit === null ? t`Using ${limitAmount(row, row.used)} · no limit` : t`Using ${limitAmount(row, row.used)} of ${limitAmount(row, row.limit)}`;
  return <>
    <p className="text-xs tabular-nums text-muted">{text}{source}{row.percent !== null ? ` · ${Math.round(row.percent)}%` : ""}</p>
    {row.percent !== null ? <ProgressBar value={row.percent / 100} label={t`${label} used`}
      tone={row.level === "limit" ? "danger" : row.level === "warning" ? "warn" : "accent"} /> : null}
  </>;
}

/** One editable limit: name, what happens at the limit, usage bar, the value (blank = no limit) and Reset to none. */
export function LimitRowView({ row, value, onChange, disabled }: {
  row: UnifiedLimit; value: string; onChange: (value: string) => void; disabled?: boolean;
}) {
  const label = limitLabel(row.key, row.label);
  const pill = row.level === "ok" ? null : LEVEL_PILL()[row.level];
  const suggested = row.suggested === null || row.suggested === undefined ? null : t`Suggested: ${limitAmount(row, row.suggested)}`;
  const unit = row.unit === "bytes" ? "MB" : row.unit === "amount" ? t`per currency` : row.unit === "per_minute" ? t`a minute` : "";
  return <li className="grid gap-x-6 gap-y-2 border-b border-line py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_auto]">
    <div className="grid min-w-0 gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-ink">{label}</p>
        {pill ? <StatusPill label={pill.label} tone={pill.tone} /> : null}
      </div>
      <p className="text-xs text-muted">{limitHint(row.key)}</p>
      <LimitUsage row={row} showSource />
    </div>
    {row.editable ? <div className="flex flex-wrap items-start gap-2">
      <div className="grid gap-1">
        <div className="flex items-center gap-2">
          <input className="desk-input w-32 tabular-nums" inputMode="numeric" aria-label={t`Limit for this space: ${label}`}
            aria-invalid={!/^(|-1|\d+)$/.test(value.trim()) || undefined}
            placeholder={t`No limit`} value={value} disabled={disabled} onChange={event => onChange(event.target.value)} />
          {unit ? <span className="text-xs text-muted">{unit}</span> : null}
        </div>
        {!value.trim() && row.platformDefault != null ? <span className="text-xs text-muted">{t`Platform default: ${limitAmount(row, row.platformDefault)}`}</span> : null}
        {!value.trim() && suggested ? <span className="text-xs text-muted">{suggested}</span> : null}
      </div>
      {value.trim() ? <button type="button" className="desk-button-ghost min-h-11" disabled={disabled}
        onClick={() => onChange("")}>{t`Reset to none`}<span className="sr-only">: {label}</span></button> : null}
    </div> : <p className="text-xs text-muted sm:max-w-40">{t`Set by the plan.`}</p>}
  </li>;
}

export const draftValue = (row: UnifiedLimit, drafts: Record<string, string>) => drafts[row.key] ?? toInput(row, row.stored);
