import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { donationsApi, giveError, type GiverFields } from "./donationsApi";

type Change = (patch: Partial<GiverFields>) => void;

/** A guest names themselves and proves their email with the one-time code (the #80 machinery). */
export function GuestIdentity({ slug, value, onChange }: { slug: string; value: GiverFields; onChange: Change }) {
  const [sentTo, setSentTo] = useState("");
  const send = useMutation({
    mutationFn: () => donationsApi.sendCode(slug, value.donor_email ?? ""),
    onSuccess: () => setSentTo(value.donor_email ?? ""),
  });
  return <fieldset className="grid gap-3">
    <legend className="text-sm font-semibold text-ink">About you</legend>
    <p className="text-sm text-muted">Giving without an account? We email you a code so nobody can give in your name.</p>
    <Field label="Your name"><input className="desk-input" required maxLength={200} autoComplete="name"
      value={value.donor_name ?? ""} onChange={event => onChange({ donor_name: event.target.value })} /></Field>
    <Field label="Email"><input className="desk-input" type="email" required autoComplete="email"
      value={value.donor_email ?? ""} onChange={event => onChange({ donor_email: event.target.value })} /></Field>
    <button type="button" className="desk-button justify-self-start" disabled={!value.donor_email || send.isPending}
      onClick={() => send.mutate()}>{send.isPending ? "Sending…" : sentTo ? "Send a new code" : "Email me a code"}</button>
    {sentTo ? <p role="status" className="text-sm text-muted">If {sentTo} can receive mail, a code is on its way.</p> : null}
    {send.error ? <p role="alert" className="text-sm text-danger">{giveError(send.error)}</p> : null}
    {sentTo ? <Field label="Code from the email"><input className="desk-input tabular-nums" required inputMode="numeric"
      autoComplete="one-time-code" maxLength={12} value={value.email_code ?? ""}
      onChange={event => onChange({ email_code: event.target.value })} /></Field> : null}
  </fieldset>;
}

/** India 80G: shown only where the space issues them; the PAN is asked for only when wanted. */
export function TaxReceiptFields({ registration, value, onChange }: {
  registration: string; value: GiverFields; onChange: Change;
}) {
  return <fieldset className="grid gap-3">
    <legend className="text-sm font-semibold text-ink">Tax-exempt receipt</legend>
    <label className="flex min-h-11 items-center gap-2 text-sm">
      <input type="checkbox" checked={Boolean(value.wants_tax_receipt)}
        onChange={event => onChange({ wants_tax_receipt: event.target.checked })} />
      I'd like an 80G receipt{registration ? ` (registration ${registration})` : ""}
    </label>
    {value.wants_tax_receipt ? <>
      <Field label="PAN" hint="Stored encrypted. Only the last four characters are ever shown back.">
        <input className="desk-input uppercase tabular-nums" required maxLength={12} autoComplete="off" spellCheck={false}
          value={value.donor_pan ?? ""} onChange={event => onChange({ donor_pan: event.target.value })} /></Field>
      <Field label="Postal address"><textarea className="desk-input" required maxLength={500} rows={3}
        autoComplete="street-address" value={value.donor_address ?? ""}
        onChange={event => onChange({ donor_address: event.target.value })} /></Field>
    </> : null}
  </fieldset>;
}
