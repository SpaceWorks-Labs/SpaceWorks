import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Copy, QrCode } from "lucide-react";
import writerWasmUrl from "zxing-wasm/writer/zxing_writer.wasm?url";

import { Field } from "../../components/ui";
import { memberRequest } from "../../lib/api";
import { memberPaymentErrorText } from "./memberPaymentErrors";

export type OfflineCollection = {
  upi: { vpa: string; payee_name: string; amount: string; currency: string; reference: string; uri: string } | null;
  instructions: string;
  claim: { id: number; reference: string; paid_on: string; status: string; decision_note: string } | null;
  claimable: boolean;
  // Parity O-B3: the member's unit gave its own instructions (its UPI QR is then not offered). Local until api.ts is regenerated.
  instructions_unit?: { id: number; name: string; code: string } | null;
};

// A function, not a module constant: `t` must run after the locale is active.
const claimText = (status: string): string | undefined => ({
  submitted: t`You told the space you paid. They'll confirm once it reaches their account.`,
  awaiting_confirmation: t`Your payment is being confirmed by a second person.`,
  confirmed: t`Your payment was confirmed.`, rejected: t`The space couldn't find this payment.`,
} as Record<string, string>)[status];

/** A QR image for the exact UPI payment, drawn in the browser from the server-built intent. */
export function useUpiQr(uri: string | null) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!uri) return;
    let active = true; let objectUrl: string | undefined;
    void import("zxing-wasm/writer").then(async writer => {
      writer.setZXingModuleOverrides({ locateFile: () => writerWasmUrl });
      const result = await writer.writeBarcode(uri, { format: "QRCode", scale: 6, addQuietZones: true });
      if (result.image && active) { objectUrl = URL.createObjectURL(result.image); setUrl(objectUrl); }
    }).catch(() => undefined);
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [uri]);
  return url;
}

/** UPI QR (exact amount) plus the "I've paid" claim; the space confirms or rejects it. */
export function OfflinePayment({ offline, onClaim, pending, error }: {
  offline: OfflineCollection; onClaim: (body: { reference: string; paid_on: string }) => void; pending: boolean; error: unknown;
}) {
  const qr = useUpiQr(offline.upi?.uri ?? null);
  const [reference, setReference] = useState("");
  const [paidOn, setPaidOn] = useState(() => new Date().toISOString().slice(0, 10));
  const [copied, setCopied] = useState(false);
  const message = memberPaymentErrorText(error);
  return <div className="mt-3 grid gap-3 rounded-lg border border-line p-3 text-ink">
    {offline.upi ? <div className="grid gap-2 sm:grid-cols-[10rem_1fr] sm:items-center">
      {qr ? <img src={qr} className="aspect-square w-40 rounded-md border border-line bg-white p-1"
        alt={t`UPI QR code to pay ${offline.upi.payee_name} ${offline.upi.amount} rupees`} /> : <QrCode aria-hidden="true" size={40} />}
      <div className="grid gap-1 text-sm">
        <p>{t`Pay `}<strong>₹{offline.upi.amount}</strong> to <strong>{offline.upi.payee_name}</strong></p>
        <p className="flex flex-wrap items-center gap-2">{t`UPI ID `}<span className="code-text">{offline.upi.vpa}</span>
          <button type="button" className="desk-button-ghost" onClick={() => { void navigator.clipboard?.writeText(offline.upi!.vpa); setCopied(true); }}>
            <Copy aria-hidden="true" size={14} />{copied ? t`Copied` : t`Copy`}</button></p>
        <p className="text-muted">{t`Add the note `}<span className="code-text">{offline.upi.reference}</span> {t` so the space can match it.`}</p>
        <a className="desk-button justify-self-start sm:hidden" href={offline.upi.uri}>{t`Open UPI app`}</a>
      </div>
    </div> : null}
    {offline.instructions_unit && offline.instructions ? <p className="text-sm font-semibold">{t`Payment instructions from ${offline.instructions_unit.name}`}</p> : null}
    {offline.instructions ? <p className="whitespace-pre-line text-sm text-muted">{offline.instructions}</p> : null}
    {offline.claim ? <p role="status" className="text-sm">{claimText(offline.claim.status) ?? offline.claim.status}
      {offline.claim.decision_note ? ` ${offline.claim.decision_note}` : ""}</p> : null}
    {offline.claimable ? <form className="grid gap-2 sm:grid-cols-[1fr_auto_auto] sm:items-end"
      onSubmit={event => { event.preventDefault(); onClaim({ reference, paid_on: paidOn }); }}>
      <Field label={t`Transaction reference (UTR)`}><input className="desk-input code-text" required minLength={6} maxLength={35}
        value={reference} onChange={event => setReference(event.target.value)} /></Field>
      <Field label={t`Paid on`}><input type="date" className="desk-input" required value={paidOn} onChange={event => setPaidOn(event.target.value)} /></Field>
      <button type="submit" className="desk-button" disabled={pending}>{t`I've paid`}</button>
    </form> : null}
    {message ? <p role="alert" className="text-sm text-danger">{message}</p> : null}
  </div>;
}

/** The member area's wiring: posts the claim for the caller's own pending charge. */
export function MemberPaymentOffline({ makerspaceId, paymentId, offline }: {
  makerspaceId: number; paymentId: number; offline: OfflineCollection;
}) {
  const client = useQueryClient();
  const claim = useMutation({
    mutationFn: (body: { reference: string; paid_on: string }) => memberRequest(
      `/member/makerspaces/${makerspaceId}/payments/${paymentId}/paid-claim`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => { void client.invalidateQueries({
      predicate: query => query.queryKey[0] === "member" && query.queryKey.includes("payments") }); },
  });
  if (!offline.upi && !offline.claim && !offline.claimable && !(offline.instructions_unit && offline.instructions)) return null;
  return <OfflinePayment offline={offline} onClaim={body => claim.mutate(body)} pending={claim.isPending} error={claim.error} />;
}
