import { t } from "@lingui/core/macro";
import { SegmentedControl } from "../../../components/ui";
import { METHOD_OPTIONS } from "./ShopOrderDialogs";
import type { PayMethod } from "./staffShopOrdersApi";

export type TillPayment = { method: PayMethod; reference: string; email: string };

/** How the buyer pays. UPI and card-machine sales need the transaction reference; cash needs nothing. */
export function PosPayment({ value, onChange, receipts }: { value: TillPayment; onChange: (next: TillPayment) => void; receipts: boolean }) {
  const needsReference = value.method !== "cash";
  return <div className="grid gap-3">
    <SegmentedControl label={t`Payment method`} value={value.method} options={METHOD_OPTIONS} fullWidth
      onChange={method => onChange({ ...value, method: method as PayMethod })} />
    <label className="grid gap-1 text-sm font-semibold text-ink">{needsReference ? t`Transaction reference` : t`Reference (optional)`}
      <input className="desk-input min-h-11 font-normal" value={value.reference} autoComplete="off"
        onChange={event => onChange({ ...value, reference: event.target.value })} /></label>
    {receipts ? <label className="grid gap-1 text-sm font-semibold text-ink">{t`Email the receipt to (optional)`}<input className="desk-input min-h-11 font-normal" type="email" value={value.email} autoComplete="off"
        onChange={event => onChange({ ...value, email: event.target.value })} /></label> : null}
  </div>;
}

export const paymentReady = (payment: TillPayment) => payment.method === "cash" || Boolean(payment.reference.trim());
