import { t } from "@lingui/core/macro";
import { shopMoney, type ShopQuote } from "./shopApi";

const percent = (bps: number | null) => bps === null ? "" : `${(bps / 100).toFixed(bps % 100 ? 2 : 0)}%`;

/** The server's priced order: lines, the member discount, the tax and what is due now. */
export function ShopQuoteSummary({ quote, title = t`Your order` }: { quote: ShopQuote; title?: string }) {
  const money = (value: string | null) => shopMoney(value, quote.currency);
  const hasTax = Number(quote.tax_total) > 0;
  return <section aria-label={title} className="grid gap-3 rounded-xl border border-line bg-surface p-4">
    <h3 className="title-section">{title}</h3>
    <table className="w-full text-sm">
      <caption className="sr-only">{title}</caption>
      <thead className="sr-only"><tr><th scope="col">{t`Item`}</th><th scope="col">{t`Amount`}</th></tr></thead>
      <tbody>
        {quote.lines.map(line => <tr key={line.variant_id} className="align-top">
          <td className="py-1 pr-3">
            <span className="block text-ink">{line.quantity} × {line.label}</span>
            {Number(line.discount) > 0 ? <span className="block text-muted">{t`Discount −${money(line.discount)}`}</span> : null}
            {hasTax && line.tax_rate_bps !== null ? <span className="block text-muted">{t`Includes ${percent(line.tax_rate_bps)} tax ${money(line.tax)}`}</span> : null}
          </td>
          <td className="py-1 text-right tabular-nums">{money(line.net)}</td>
        </tr>)}
      </tbody>
    </table>
    <dl className="grid gap-1 border-t border-line pt-3 text-sm">
      <div className="flex justify-between gap-3"><dt className="text-muted">{t`Subtotal`}</dt><dd className="tabular-nums">{money(quote.subtotal)}</dd></div>
      {Number(quote.discount_total) > 0 ? <div className="flex justify-between gap-3">
        <dt className="text-muted">{quote.discount_name || t`Discount`}</dt><dd className="tabular-nums">−{money(quote.discount_total)}</dd></div> : null}
      {hasTax ? <div className="flex justify-between gap-3"><dt className="text-muted">{quote.tax_inclusive ? t`Tax included` : t`Tax`}</dt>
        <dd className="tabular-nums">{money(quote.tax_total)}</dd></div> : null}
      <div className="flex justify-between gap-3 text-base font-semibold text-ink"><dt>{t`Total`}</dt><dd className="tabular-nums">{money(quote.total)}</dd></div>
      {quote.amount_due !== quote.total ? <div className="flex justify-between gap-3 font-semibold text-ink"><dt>{t`Due now`}</dt>
        <dd className="tabular-nums">{money(quote.amount_due)}</dd></div> : null}
    </dl>
  </section>;
}
