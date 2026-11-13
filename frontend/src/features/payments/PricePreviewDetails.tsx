import { plural, t } from "@lingui/core/macro";
import { BadgePercent, Coins, HandCoins } from "lucide-react";

import type { PricingPublicQuote } from "./usePriceQuote";
import { money, quantityText } from "./usePriceQuote";
import { IncludedHoursLine, type IncludedHoursSummary } from "./IncludedHoursLine";

const positive = (value: string | null | undefined) => value !== null && value !== undefined && Number(value) > 0;
const row = "flex items-baseline justify-between gap-3";

/** The priced lines, any member discount and any waiver. */
export function QuoteLines({ data }: { data: PricingPublicQuote }) {
  const { quote } = data;
  return <>
    <ul className="grid gap-2">
      {quote.lines.map((line, index) => <li key={`${line.component}-${index}`} className={row}>
        <span className="min-w-0">
          <span className="block text-ink">{line.label}</span>
          <span className="block text-xs text-muted tabular-nums">{quantityText(line.quantity)} × {money(line.unit_amount, quote.currency)}</span>
        </span>
        <span className="shrink-0 tabular-nums text-ink">{money(line.net, quote.currency)}</span>
      </li>)}
    </ul>
    {positive(quote.discount_total) ? <p className={`${row} text-success-ink`}>
      <span className="flex items-center gap-2"><BadgePercent aria-hidden="true" className="h-4 w-4" />{t`Member discount${quote.discount?.name ? ` (${quote.discount.name})` : ""}`}</span>
      <span className="tabular-nums">−{money(quote.discount_total, quote.currency)}</span>
    </p> : null}
    {quote.waiver ? <p className="flex items-center gap-2 text-ink"><HandCoins aria-hidden="true" className="h-4 w-4 text-muted" />{t`Fees waived`}</p> : null}
    {/* Decision 221(d): not yet in the generated schema; present only on a booking quote. */}
    <IncludedHoursLine info={(quote as { included_hours?: IncludedHoursSummary | null }).included_hours} />
  </>;
}

/** The bottom line: tax split when the space charges tax, then the total. */
export function QuoteTotals({ data }: { data: PricingPublicQuote }) {
  const { quote, tax } = data;
  const taxed = tax.mode !== "none";
  return <dl className="grid gap-1 border-t border-line pt-2">
    {taxed && !tax.inclusive ? <>
      <div className={row}><dt className="text-muted">{t`Before tax`}</dt><dd className="tabular-nums">{money(tax.net, quote.currency)}</dd></div>
      <div className={row}><dt className="text-muted">{t`Tax`}</dt><dd className="tabular-nums">{money(tax.tax, quote.currency)}</dd></div>
    </> : null}
    <div className={`${row} font-semibold text-ink`}><dt>{t`Total`}</dt><dd className="tabular-nums">{money(taxed ? tax.gross : quote.total, quote.currency)}</dd></div>
    {taxed && tax.inclusive ? <div className={`${row} text-xs text-muted`}><dt>{t`Includes tax`}</dt>
      <dd className="tabular-nums">{t`${money(tax.tax, quote.currency)} (before tax ${money(tax.net, quote.currency)})`}</dd></div> : null}
  </dl>;
}

/** Deposit, member price hint, notes, late/damage/lost policy and the refund summary. */
export function QuoteExtras({ data }: { data: PricingPublicQuote }) {
  const { quote, deposit, policy } = data;
  const currency = quote.currency;
  return <>
    {deposit ? <p className="flex items-center gap-2 text-ink"><Coins aria-hidden="true" className="h-4 w-4 text-muted" />
      <span>{t`Refundable deposit: `}<span className="tabular-nums">{money(deposit.amount, currency)}</span>
        <span className="text-muted"> {t` (not part of the total)`}</span></span></p> : null}
    {data.members_total !== null && data.members_total !== undefined
      ? <p className="text-muted">{t`Members pay `}<span className="tabular-nums text-ink">{money(data.members_total, currency)}</span></p> : null}
    {quote.notes.map(note => <p key={note} className="text-xs text-muted">{note}</p>)}
    {policy ? <div className="grid gap-1 text-xs text-muted">
      {positive(policy.late_per_day) ? <p>{t`Late returns: ${money(policy.late_per_day, currency)} per day`}{policy.grace_days ? ` ${plural(policy.grace_days, { one: "after # grace day", other: "after # grace days" })}` : ""}
        {positive(policy.late_cap) ? t`, up to ${money(policy.late_cap!, currency)}` : ""}.</p> : null}
      {positive(policy.damage_default) ? <p>{t`Damage charge: ${money(policy.damage_default, currency)}.`}</p> : null}
      {positive(policy.lost_default) ? <p>{t`Lost item charge: ${money(policy.lost_default, currency)}.`}</p> : null}
      {policy.damage_lost_text ? <p>{policy.damage_lost_text}</p> : null}
    </div> : null}
    {data.refund_summary ? <p className="text-xs text-muted">{data.refund_summary}</p> : null}
  </>;
}
