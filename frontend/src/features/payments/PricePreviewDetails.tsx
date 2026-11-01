import { BadgePercent, Coins, HandCoins } from "lucide-react";

import type { PricingPublicQuote } from "./usePriceQuote";
import { money, quantityText } from "./usePriceQuote";

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
      <span className="flex items-center gap-2"><BadgePercent aria-hidden="true" className="h-4 w-4" />Member discount{quote.discount?.name ? ` (${quote.discount.name})` : ""}</span>
      <span className="tabular-nums">−{money(quote.discount_total, quote.currency)}</span>
    </p> : null}
    {quote.waiver ? <p className="flex items-center gap-2 text-ink"><HandCoins aria-hidden="true" className="h-4 w-4 text-muted" />Fees waived</p> : null}
  </>;
}

/** The bottom line: tax split when the space charges tax, then the total. */
export function QuoteTotals({ data }: { data: PricingPublicQuote }) {
  const { quote, tax } = data;
  const taxed = tax.mode !== "none";
  return <dl className="grid gap-1 border-t border-line pt-2">
    {taxed && !tax.inclusive ? <>
      <div className={row}><dt className="text-muted">Before tax</dt><dd className="tabular-nums">{money(tax.net, quote.currency)}</dd></div>
      <div className={row}><dt className="text-muted">Tax</dt><dd className="tabular-nums">{money(tax.tax, quote.currency)}</dd></div>
    </> : null}
    <div className={`${row} font-semibold text-ink`}><dt>Total</dt><dd className="tabular-nums">{money(taxed ? tax.gross : quote.total, quote.currency)}</dd></div>
    {taxed && tax.inclusive ? <div className={`${row} text-xs text-muted`}><dt>Includes tax</dt>
      <dd className="tabular-nums">{money(tax.tax, quote.currency)} (before tax {money(tax.net, quote.currency)})</dd></div> : null}
  </dl>;
}

/** Deposit, member price hint, notes, late/damage/lost policy and the refund summary. */
export function QuoteExtras({ data }: { data: PricingPublicQuote }) {
  const { quote, deposit, policy } = data;
  const currency = quote.currency;
  return <>
    {deposit ? <p className="flex items-center gap-2 text-ink"><Coins aria-hidden="true" className="h-4 w-4 text-muted" />
      <span>Refundable deposit: <span className="tabular-nums">{money(deposit.amount, currency)}</span>
        <span className="text-muted"> (not part of the total)</span></span></p> : null}
    {data.members_total !== null && data.members_total !== undefined
      ? <p className="text-muted">Members pay <span className="tabular-nums text-ink">{money(data.members_total, currency)}</span></p> : null}
    {quote.notes.map(note => <p key={note} className="text-xs text-muted">{note}</p>)}
    {policy ? <div className="grid gap-1 text-xs text-muted">
      {positive(policy.late_per_day) ? <p>Late returns: {money(policy.late_per_day, currency)} per day
        {policy.grace_days ? ` after ${policy.grace_days} grace day${policy.grace_days === 1 ? "" : "s"}` : ""}
        {positive(policy.late_cap) ? `, up to ${money(policy.late_cap!, currency)}` : ""}.</p> : null}
      {positive(policy.damage_default) ? <p>Damage charge: {money(policy.damage_default, currency)}.</p> : null}
      {positive(policy.lost_default) ? <p>Lost item charge: {money(policy.lost_default, currency)}.</p> : null}
      {policy.damage_lost_text ? <p>{policy.damage_lost_text}</p> : null}
    </div> : null}
    {data.refund_summary ? <p className="text-xs text-muted">{data.refund_summary}</p> : null}
  </>;
}
