import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ScreenHelp } from "../../help/HelpLink";
import { collectAtDesk, guestPayLink } from "./staffTicketingApi";

const METHODS = [["cash", "Cash"], ["upi", "UPI"], ["bank_transfer", "Bank transfer"], ["card_machine", "Card machine"], ["cheque", "Cheque"], ["other", "Other"]] as const;

/** G33: take a pending ticket payment at the check-in desk -- a receipt, or a pay-now link for the
 * attendee's phone -- and send the pay link for a guest just added. Money goes through the ledger. */
export function DeskCollectPanel({ registrationId, onCollected }: { registrationId: number; onCollected?: () => void }) {
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const collect = useMutation({ mutationFn: (terminal: boolean) => collectAtDesk(registrationId, { terminal, method: terminal ? undefined : method, reference }),
    onSuccess: () => onCollected?.() });
  const link = useMutation({ mutationFn: (send: boolean) => guestPayLink(registrationId, send) });
  const error = collect.error ?? link.error;
  const url = collect.data?.checkout_url || link.data?.pay_link;
  return <section className="grid gap-3 rounded-xl border border-line p-3" aria-label="Collect payment">
    <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold text-ink">This ticket is not paid yet</p>
      <ScreenHelp screen="events.desk-collect" className="" /></div>
    <div className="flex flex-wrap items-end gap-2">
      <label className="grid gap-1 text-sm">Received as<select className="desk-input" value={method} onChange={event => setMethod(event.target.value)}>
        {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Reference<input className="desk-input" maxLength={64} value={reference} onChange={event => setReference(event.target.value)} /></label>
      <button type="button" className="desk-button-primary" disabled={collect.isPending} onClick={() => collect.mutate(false)}>Record payment</button>
      <button type="button" className="desk-button" disabled={collect.isPending} onClick={() => collect.mutate(true)}>Pay on phone</button>
      <button type="button" className="desk-button" disabled={link.isPending} onClick={() => link.mutate(true)}>Email pay link</button>
    </div>
    {collect.data && !collect.data.checkout_url ? <p role="status" className="text-sm text-success">Payment recorded.</p> : null}
    {link.data?.sent ? <p role="status" className="text-sm text-muted">Pay link emailed.</p> : null}
    {url ? <p className="break-all text-sm"><a className="underline" href={url} target="_blank" rel="noreferrer">{url}</a></p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
  </section>;
}
