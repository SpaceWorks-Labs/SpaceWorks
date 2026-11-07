import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { requestEmailCode, shopErrorMessage } from "./shopApi";

export type GuestIdentity = { name: string; email: string; code: string };
export const emptyGuest: GuestIdentity = { name: "", email: "", code: "" };
export const guestReady = (guest: GuestIdentity) => Boolean(guest.name.trim() && guest.email.includes("@") && guest.code.trim());

/** Guest checkout (#80): a name, an email and the one-time code the shop emails to it. */
export function GuestIdentityFields({ slug, value, onChange, onSignIn }: {
  slug: string; value: GuestIdentity; onChange: (next: GuestIdentity) => void; onSignIn: () => void;
}) {
  const send = useMutation({ mutationFn: () => requestEmailCode(slug, value.email.trim()) });
  const set = (patch: Partial<GuestIdentity>) => onChange({ ...value, ...patch });
  return <fieldset className="grid gap-3">
    <legend className="title-section mb-1">{t`Your details`}</legend>
    <p className="text-sm text-muted">{t`Order as a guest, or `}<button type="button" className="font-semibold text-brand-ink underline underline-offset-4" onClick={onSignIn}>{t`sign in`}</button> {t` to use your account.`}</p>
    <Field label={t`Your name`}><input className="desk-input min-h-11" autoComplete="name" value={value.name}
      onChange={event => set({ name: event.target.value })} /></Field>
    <Field label={t`Email`} hint={t`We email a one-time code here, and your order updates.`}><input className="desk-input min-h-11" type="email"
      autoComplete="email" value={value.email} onChange={event => { set({ email: event.target.value, code: "" }); send.reset(); }} /></Field>
    <button type="button" className="desk-button min-h-11 justify-self-start" disabled={!value.email.includes("@") || send.isPending}
      onClick={() => send.mutate()}>{send.isPending ? t`Sending…` : send.isSuccess ? t`Send the code again` : t`Email me a code`}</button>
    <p role="status" className="text-sm text-muted">{send.isSuccess ? t`Code sent to ${value.email.trim()}. It may take a minute.` : ""}</p>
    {send.error ? <p role="alert" className="text-sm text-danger">{shopErrorMessage(send.error)}</p> : null}
    {send.isSuccess ? <Field label={t`Code from the email`}><input className="desk-input min-h-11 tracking-widest" inputMode="numeric"
      autoComplete="one-time-code" value={value.code} onChange={event => set({ code: event.target.value.trim() })} /></Field> : null}
  </fieldset>;
}
