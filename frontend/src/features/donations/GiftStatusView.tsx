import { t } from "@lingui/core/macro";
import { formatMoney } from "../../lib/money";
import { Card, StatusPill } from "../../components/ui";
import { useUpiQr } from "../members/MemberPaymentOffline";
import { type GiftStatus } from "./donationsApi";

const STATUS: Record<GiftStatus["status"], { label: string; tone: "success" | "warn" | "neutral" }> = {
  paid: { label: t`Received`, tone: "success" }, pending: { label: t`Waiting for payment`, tone: "warn" },
  cancelled: { label: t`Cancelled`, tone: "neutral" },
};

/** How to pay a gift offline: the space's own instructions and, with UPI, a QR for the exact amount. */
export function OfflineGiftInstructions({ gift }: { gift: GiftStatus }) {
  const qr = useUpiQr(gift.offline?.upi?.uri ?? null);
  if (!gift.offline || (!gift.offline.instructions && !gift.offline.upi)) {
    return <p className="text-sm text-muted">{t`The space will tell you how to pay. Keep this page to check on your gift.`}</p>;
  }
  return <div className="grid gap-3">
    <h3 className="title-section">{t`Pay offline`}</h3>
    {gift.offline.instructions ? <p className="whitespace-pre-wrap text-sm">{gift.offline.instructions}</p> : null}
    {gift.offline.upi ? <div className="grid gap-2">
      {qr ? <img src={qr} alt={t`UPI QR code to pay ${formatMoney(gift.amount, gift.currency)}`} width={180} height={180}
        className="rounded-md border border-line bg-white p-2" /> : null}
      {gift.offline.upi.vpa ? <p className="text-sm">{t`UPI ID `}<span className="code-text">{gift.offline.upi.vpa}</span></p> : null}
    </div> : null}
  </div>;
}

/** One gift as its giver sees it: amount, where it went, status, receipts and how to pay. */
export function GiftStatusView({ gift, taxReceiptHref, onPayOnline, paying = false }: {
  gift: GiftStatus; taxReceiptHref?: string; onPayOnline?: () => void; paying?: boolean;
}) {
  const status = STATUS[gift.status];
  return <Card><div className="grid gap-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-2xl font-semibold tabular-nums text-ink">{formatMoney(gift.amount, gift.currency)}</p>
      <StatusPill label={status.label} tone={status.tone} />
    </div>
    <dl className="grid gap-2 text-sm sm:grid-cols-2">
      <div><dt className="text-muted">{t`To`}</dt><dd>{gift.makerspace}{gift.campaign ? ` · ${gift.campaign}` : ""}</dd></div>
      {gift.receipt_number ? <div><dt className="text-muted">{t`Receipt`}</dt><dd className="tabular-nums">{gift.receipt_number}</dd></div> : null}
      {gift.donor_pan_masked ? <div><dt className="text-muted">PAN</dt><dd className="tabular-nums">{gift.donor_pan_masked}</dd></div> : null}
      {gift.tax_receipt_number ? <div><dt className="text-muted">{t`Tax receipt`}</dt><dd className="tabular-nums">{gift.tax_receipt_number}</dd></div> : null}
    </dl>
    {gift.receipt_note ? <p className="text-sm text-muted">{gift.receipt_note}</p> : null}
    {gift.status === "paid" ? <p className="text-sm">{t`Thank you. Your gift has been received.`}</p> : null}
    {gift.tax_receipt_number && taxReceiptHref ? <a className="desk-button justify-self-start" href={taxReceiptHref}
      rel="noopener" download>{t`Download tax receipt (PDF)`}</a> : null}
    {gift.status === "pending" && gift.online_available && onPayOnline ? <button type="button" className="desk-button-primary justify-self-start"
      disabled={paying} onClick={onPayOnline}>{paying ? t`Opening checkout…` : t`Pay online`}</button> : null}
    {gift.status === "pending" ? <OfflineGiftInstructions gift={gift} /> : null}
  </div></Card>;
}
