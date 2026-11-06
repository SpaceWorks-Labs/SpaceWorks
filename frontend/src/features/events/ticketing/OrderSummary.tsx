import { t } from "@lingui/core/macro";
import { ShoppingBag } from "lucide-react";
import { money, policyLine, type OrderQuote } from "./ticketingApi";

/** The priced basket a buyer confirms: every line, the booking fee, the total and the refund policy. */
export function OrderSummary({ quote }: { quote: OrderQuote }) {
  const { currency, lines, total } = quote.quote;
  return <section aria-label={t`Order summary`} className="grid gap-3 rounded-card border border-line p-4">
    <h3 className="flex items-center gap-2 font-semibold text-ink"><ShoppingBag aria-hidden="true" size={18} />{t`Your order`}</h3>
    <dl className="grid gap-2 text-sm">
      {lines.map((line, index) => <div key={index} className="flex justify-between gap-4">
        <dt>{String(line.detail?.label ?? line.label)}{Number(line.quantity) !== 1 && line.component !== "booking_fee" ? ` × ${Number(line.quantity)}` : ""}</dt>
        <dd className="tabular-nums">{Number(line.discount) > 0
          ? <><s className="text-muted">{money(line.gross, currency)}</s> {money(line.net, currency)}</> : money(line.net, currency)}</dd>
      </div>)}
      <div className="flex justify-between gap-4 border-t border-line pt-2 text-base font-semibold text-ink">
        <dt>{t`Total`}</dt><dd className="tabular-nums">{money(total, currency)}</dd>
      </div>
    </dl>
    <p className="text-sm text-muted">{quote.seats === 1 ? t`1 place` : `${quote.seats} places`}. Places for other
      people are held until each person signs in and claims theirs.</p>
    <p className="text-sm text-muted"><span className="font-semibold text-ink">{t`Refund policy: `}</span>{policyLine(quote.policy)}</p>
  </section>;
}
