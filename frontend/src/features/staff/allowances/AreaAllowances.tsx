import { t } from "@lingui/core/macro";
import { Callout, ProgressBar, StatusPill } from "../../../components/ui";
import { limitLabel } from "../platformSpaces/limitCopy";
import { amount, limitReachedText, useStaffAllowances, type AllowanceArea, type AllowanceRow } from "./allowancesApi";

/** Which allowance area a staff tab belongs to; the dashboard shows every area the person manages. */
const TAB_AREA: Record<string, AllowanceArea | "all"> = {
  dashboard: "all", inventory: "inventory", machines: "machines", events: "events", bookings: "bookings", members: "members",
  shop: "shop", users: "staff", qr: "qr", devices: "devices", donations: "donations",
};

function usedText(row: AllowanceRow) {
  if (row.used === null) return row.unit === "bytes" ? t`Up to ${amount(row.limit, row.unit)} per file` : t`Limit: ${amount(row.limit, row.unit)}`;
  return t`${amount(row.used, row.unit)} of ${amount(row.limit, row.unit)} used · ${amount(row.remaining ?? 0, row.unit)} left`;
}

function Meter({ row }: { row: AllowanceRow }) {
  const tone = row.level === "limit" ? "danger" : row.level === "warning" ? "warn" : "accent";
  return <li className="grid gap-1">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-sm font-semibold text-ink">{limitLabel(row.key, row.label)}</span>
      {row.level === "limit" ? <StatusPill label={t`At limit`} tone="danger" /> : row.level === "warning" ? <StatusPill label={t`Near limit`} tone="warn" /> : null}
    </div>
    <p className="text-sm text-muted">{usedText(row)}</p>
    {row.percent !== null ? <ProgressBar value={row.percent / 100} tone={tone} label={t`${limitLabel(row.key, row.label)} used`} /> : null}
  </li>;
}

/**
 * Remaining allowance for the limits this person manages (#234 addendum 3(a)): a warning at 80 %,
 * a stop at 100 %. Renders nothing when nothing is limited (hosting off, an own space, no limits set).
 */
export function AreaAllowances({ makerspaceId, tab }: { makerspaceId: number; tab: string }) {
  const area = TAB_AREA[tab];
  const query = useStaffAllowances(makerspaceId);
  const all = query.data?.rows;
  if (!area || !Array.isArray(all)) return null;
  const rows = all.filter(row => area === "all" || row.areas.includes(area));
  if (!rows.length) return null;
  const full = rows.filter(row => row.level === "limit");
  const near = rows.filter(row => row.level === "warning");
  return <section aria-labelledby={`allowances-${tab}`} className="desk-panel mb-4 grid gap-3 p-4">
    <h2 id={`allowances-${tab}`} className="title-panel">{area === "all" ? t`Plan & usage` : t`Limits for this area`}</h2>
    {full.map(row => <Callout key={row.key} size="inline" tone="danger" lead={limitReachedText(row)} />)}
    {near.map(row => <Callout key={row.key} size="inline" tone="warn"
      lead={t`${limitLabel(row.key, row.label)}: ${Math.round(row.percent ?? 0)}% used.`} body={t`New ones are refused at the limit.`} />)}
    <ul className="grid gap-4 sm:grid-cols-2" aria-label={t`Allowances`}>{rows.map(row => <Meter key={row.key} row={row} />)}</ul>
  </section>;
}
