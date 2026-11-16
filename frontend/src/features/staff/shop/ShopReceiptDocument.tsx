import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { shopMoney } from "../../shop/shopApi";
import type { ShopReceipt } from "./staffShopOrdersApi";
import { METHOD_LABELS } from "./staffShopOrdersApi";

export type PaperFormat = "80mm" | "a4";
const percent = (bps: number | null) => bps === null ? "" : `${bps / 100}%`;

/** The printable document. 80 mm is a till slip (one column); A4 is a full table with HSN and tax per line. */
export function ShopReceiptDocument({ receipt, format }: { receipt: ShopReceipt; format: PaperFormat }) {
  const money = (value: string | null) => shopMoney(value, receipt.currency);
  const slip = format === "80mm";
  const hasTax = Number(receipt.tax_total) > 0;
  return <article aria-label={receipt.document_title || t`Receipt`} data-format={format}
    className={`shop-receipt bg-panel text-ink ${slip ? "shop-receipt-80" : "shop-receipt-a4"} grid gap-3 rounded-xl border border-line p-4`}>
    <header className={slip ? "grid gap-0.5 text-center" : "flex flex-wrap justify-between gap-4"}>
      <div><p className="text-base font-semibold">{receipt.space_name}</p>
        {receipt.supplier_gstin ? <p>{t`GSTIN ${receipt.supplier_gstin}`}</p> : null}</div>
      <div className={slip ? "" : "text-right"}><p className="font-semibold">{receipt.document_title || t`Receipt`}</p>
        {receipt.document_number ? <p>{t`No. ${receipt.document_number}`}</p> : null}
        {receipt.issued_at ? <p>{new Date(receipt.issued_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" })}</p> : null}
        <p>{t`Order #${receipt.order_id}${receipt.pickup_code ? ` · ${receipt.pickup_code}` : ""}`}</p></div>
    </header>
    {receipt.buyer_name ? <p>{t`Buyer: ${receipt.buyer_name}`}</p> : null}
    <table>
      <caption className="sr-only">{t`Items`}</caption>
      <thead><tr className="border-b border-line text-left">
        <th scope="col">{t`Item`}</th>{slip ? null : <><th scope="col">HSN</th><th scope="col" className="text-right">{t`Unit`}</th></>}
        <th scope="col" className="text-right">{t`Qty`}</th>{slip || !hasTax ? null : <th scope="col" className="text-right">{t`Tax`}</th>}
        <th scope="col" className="text-right">{t`Amount`}</th></tr></thead>
      <tbody>{receipt.lines.map((line, index) => <tr key={`${line.label}-${index}`} className="border-b border-line">
        <td>{line.label}{line.sku && !slip ? <span className="block text-xs">SKU {line.sku}</span> : null}
          {Number(line.discount_amount) > 0 ? <span className="block text-xs">{t`Discount −${money(line.discount_amount)}`}</span> : null}
          {slip && hasTax && line.tax_rate_bps !== null ? <span className="block text-xs">{t`Tax ${percent(line.tax_rate_bps)} ${money(line.tax_amount)}`}</span> : null}</td>
        {slip ? null : <><td>{line.hsn_code}</td><td className="text-right tabular-nums">{money(line.unit_amount)}</td></>}
        <td className="text-right tabular-nums">{line.quantity}</td>
        {slip || !hasTax ? null : <td className="text-right tabular-nums">{percent(line.tax_rate_bps)} {money(line.tax_amount)}</td>}
        <td className="text-right tabular-nums">{money(line.line_total)}</td></tr>)}</tbody>
    </table>
    <dl className="grid gap-0.5">
      <div className="flex justify-between gap-2"><dt>{t`Subtotal`}</dt><dd className="tabular-nums">{money(receipt.subtotal)}</dd></div>
      {Number(receipt.discount_total) > 0 ? <div className="flex justify-between gap-2"><dt>{t`Discount`}</dt><dd className="tabular-nums">−{money(receipt.discount_total)}</dd></div> : null}
      {hasTax ? <div className="flex justify-between gap-2"><dt>{t`Tax included`}</dt><dd className="tabular-nums">{money(receipt.tax_total)}</dd></div> : null}
      <div className="flex justify-between gap-2 font-semibold"><dt>{t`Total`}</dt><dd className="tabular-nums">{money(receipt.total)}</dd></div>
    </dl>
    <p className="font-semibold">{receipt.paid ? t`Paid${receipt.method ? ` · ${METHOD_LABELS[receipt.method] ?? receipt.method}` : ""}` : t`Not paid yet`}</p>
    {receipt.notes.map(note => <p key={note} className="text-xs">{note}</p>)}
  </article>;
}
