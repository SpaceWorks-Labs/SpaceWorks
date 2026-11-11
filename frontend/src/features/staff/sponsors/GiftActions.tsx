import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill } from "../../../components/ui";
import { financeError } from "../../finance/financeApi";
import { GIFT_STATUS, donationStaffApi, type StaffDonation } from "./staffDonationsApi";

type Mode = "cancel" | "return" | "received" | null;
const METHODS = [["cash", t`Cash`], ["upi", "UPI"], ["bank_transfer", t`Bank transfer`], ["card_machine", t`Card machine`],
  ["cheque", t`Cheque`], ["other", t`Other`]] as const;

/** One gift's status and what its owner may do: receipts, settling, a paid claim, cancel or return. */
export function GiftActions({ makerspaceId, gift, canRecord, taxOn }: {
  makerspaceId: number; gift: StaffDonation; canRecord: boolean; taxOn: boolean;
}) {
  const client = useQueryClient();
  const [mode, setMode] = useState<Mode>(null);
  const [reason, setReason] = useState("");
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const refresh = () => void client.invalidateQueries({ queryKey: ["staff-donations", makerspaceId] });
  const cancel = useMutation({ mutationFn: (reason: string) => donationStaffApi.cancel(makerspaceId, gift.id, reason), onSuccess: refresh });
  const back = useMutation({ mutationFn: (reason: string) => donationStaffApi.openReturn(makerspaceId, gift.id, reason), onSuccess: refresh });
  const received = useMutation({ mutationFn: () => donationStaffApi.markReceived(makerspaceId, gift.payment_id!, {
    method, reference, received_at: new Date().toISOString() }), onSuccess: refresh });
  const claim = useMutation({ mutationFn: (confirm: boolean) => donationStaffApi.decideClaim(makerspaceId, gift.id, confirm),
    onSuccess: refresh });
  const reissue = useMutation({ mutationFn: () => donationStaffApi.reissue(makerspaceId, gift.id), onSuccess: refresh });
  const pdf = useMutation({ mutationFn: () => donationStaffApi.taxReceipt(makerspaceId, gift) });
  const error = cancel.error || back.error || received.error || claim.error || reissue.error || pdf.error;
  const toggle = (next: Mode) => setMode(mode === next ? null : next);
  const pending = gift.status === "pending";
  return <div className="grid justify-items-end gap-2">
    <StatusPill label={GIFT_STATUS[gift.status].label} tone={GIFT_STATUS[gift.status].tone} />
    {gift.open_claim ? <p className="text-xs text-muted">{t`Giver says they paid: reference ${gift.open_claim.reference} on ${gift.open_claim.paid_on}`}</p> : null}
    <div className="flex flex-wrap justify-end gap-2">
      {taxOn && gift.tax_receipt_number ? <button type="button" className="desk-button-ghost" disabled={pdf.isPending}
        onClick={() => pdf.mutate()}>{t`Tax receipt`}</button> : null}
      {canRecord && gift.status === "paid" ? <button type="button" className="desk-button-ghost" disabled={reissue.isPending}
        onClick={() => reissue.mutate()}>{t`Send receipt again`}</button> : null}
      {canRecord && pending && gift.open_claim ? <>
        <button type="button" className="desk-button" disabled={claim.isPending} onClick={() => claim.mutate(true)}>{t`Confirm payment`}</button>
        <button type="button" className="desk-button-ghost" disabled={claim.isPending} onClick={() => claim.mutate(false)}>{t`Reject claim`}</button>
      </> : null}
      {canRecord && pending && gift.payment_id && !gift.open_claim ? <button type="button" className="desk-button-ghost"
        aria-expanded={mode === "received"} onClick={() => toggle("received")}>{t`Mark received`}</button> : null}
      {canRecord && pending ? <button type="button" className="desk-button-ghost"
        aria-expanded={mode === "cancel"} onClick={() => toggle("cancel")}>{t`Cancel`}</button> : null}
      {canRecord && gift.status === "paid" ? <button type="button" className="desk-button-ghost"
        aria-expanded={mode === "return"} onClick={() => toggle("return")}>{t`Return…`}</button> : null}
    </div>
    {mode === "received" ? <form className="flex flex-wrap items-end justify-end gap-2" aria-label={t`Mark this gift received`}
      onSubmit={event => { event.preventDefault(); received.mutate(undefined, { onSuccess: () => setMode(null) }); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`How it was paid`}<select className="desk-input" value={method}
        onChange={event => setMethod(event.target.value)}>{METHODS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Reference (optional)`}<input className="desk-input" maxLength={64}
        value={reference} onChange={event => setReference(event.target.value)} /></label>
      <button type="submit" className="desk-button" disabled={received.isPending}>{t`Record as received`}</button>
    </form> : null}
    {mode === "cancel" || mode === "return" ? <form className="flex flex-wrap items-end justify-end gap-2"
      aria-label={mode === "cancel" ? t`Cancel this gift` : t`Return this gift`}
      onSubmit={event => { event.preventDefault(); (mode === "cancel" ? cancel : back).mutate(reason, { onSuccess: () => setMode(null) }); }}>
      <label className="grid gap-1 text-sm font-semibold text-ink">{mode === "cancel" ? t`Why cancel? (optional)` : t`Why return it?`}
        <input className="desk-input" maxLength={500} required={mode === "return"} value={reason}
          onChange={event => setReason(event.target.value)} /></label>
      <button type="submit" className="desk-button" disabled={cancel.isPending || back.isPending}>
        {mode === "cancel" ? t`Cancel gift` : t`Open refund case`}</button>
    </form> : null}
    {back.isSuccess ? <p role="status" className="text-xs text-muted">{t`Refund case opened. Decide it under Refunds.`}</p> : null}
    {reissue.isSuccess ? <p role="status" className="text-xs text-muted">{t`Receipt sent again.`}</p> : null}
    {error ? <p role="alert" className="text-xs text-danger">{financeError(error)}</p> : null}
  </div>;
}
