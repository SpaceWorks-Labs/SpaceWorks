import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { donationsApi, giveError } from "./donationsApi";

/** "I've paid": a guest tells the space they paid offline (UPI reference); staff confirm or reject it. */
export function GuestPaidClaim({ token }: { token: string }) {
  const [reference, setReference] = useState("");
  const [paidOn, setPaidOn] = useState(() => new Date().toISOString().slice(0, 10));
  const claim = useMutation({ mutationFn: () => donationsApi.claim(token, { reference, paid_on: paidOn }) });
  if (claim.isSuccess) {
    return <p role="status" className="text-sm">Thanks. The space will confirm your payment and send your receipt.</p>;
  }
  return <form className="grid gap-3" aria-label="Tell the space you paid" onSubmit={event => { event.preventDefault(); claim.mutate(); }}>
    <h3 className="title-section">Already paid?</h3>
    <div className="flex flex-wrap items-end gap-2">
      <label className="grid gap-1 text-sm font-semibold text-ink">Transaction reference (UTR)
        <input className="desk-input min-h-11" required maxLength={64} value={reference}
          onChange={event => setReference(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">Paid on
        <input className="desk-input min-h-11" type="date" required value={paidOn}
          onChange={event => setPaidOn(event.target.value)} /></label>
      <button type="submit" className="desk-button min-h-11" disabled={claim.isPending}>Tell the space</button>
    </div>
    {claim.error ? <p role="alert" className="text-sm text-danger">{giveError(claim.error)}</p> : null}
  </form>;
}
