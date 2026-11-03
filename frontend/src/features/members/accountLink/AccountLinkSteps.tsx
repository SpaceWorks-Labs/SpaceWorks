import { useId } from "react";
import { Field } from "../../../components/ui";
import type { MergeMethod } from "./accountLinkApi";

const METHODS: { value: MergeMethod; label: string; hint: string }[] = [
  { value: "credentials", label: "Its password and authenticator", hint: "Sign in to the other account here, once." },
  { value: "email_codes", label: "Codes sent to both emails", hint: "We email one code to this account and one to the other account." },
];

export function StartStep({ identifier, method, onIdentifier, onMethod }: {
  identifier: string; method: MergeMethod; onIdentifier: (value: string) => void; onMethod: (value: MergeMethod) => void;
}) {
  const legend = useId();
  return <div className="grid gap-5">
    <p className="text-sm text-muted">Nothing changes until you review what moves and confirm. Accounts are never linked on email alone.</p>
    <Field label="Username or email of the other account">
      <input className="desk-input min-h-11" value={identifier} autoComplete="off" autoCapitalize="none" spellCheck={false}
        maxLength={254} onChange={event => onIdentifier(event.target.value)} />
    </Field>
    <div role="radiogroup" aria-labelledby={legend} className="grid gap-3">
      <p id={legend} className="text-sm font-semibold text-ink">How will you prove it's yours?</p>
      <div className="grid gap-3 md:grid-cols-2">{METHODS.map(option => <label key={option.value}
        className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-control border p-4 ${method === option.value ? "border-accent bg-accent-soft" : "border-line"}`}>
        <input type="radio" name="account-link-method" className="mt-1 h-5 w-5 shrink-0 accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          value={option.value} checked={method === option.value} onChange={() => onMethod(option.value)} />
        <span className="grid gap-1"><span className="font-semibold text-ink">{option.label}</span>
          <span className="text-sm text-muted">{option.hint}</span></span>
      </label>)}</div>
    </div>
  </div>;
}

export type ProofFields = { password: string; otp: string; survivorCode: string; sourceCode: string };
const digits = (value: string) => value.replace(/\s+/g, "");

export function ProveStep({ method, identifier, fields, onChange, onResend, resending, resent }: {
  method: MergeMethod; identifier: string; fields: ProofFields; onChange: (fields: ProofFields) => void;
  onResend: () => void; resending: boolean; resent: boolean;
}) {
  const set = (key: keyof ProofFields, value: string) => onChange({ ...fields, [key]: value });
  if (method === "credentials") return <div className="grid gap-4">
    <p className="text-sm text-muted">Enter the password and a current authenticator code for <strong className="text-ink">{identifier}</strong>. You stay signed in to this account.</p>
    <Field label="Password of the other account">
      <input className="desk-input min-h-11" type="password" autoComplete="off" value={fields.password}
        onChange={event => set("password", event.target.value)} />
    </Field>
    <Field label="Authenticator code" hint="The 6-digit code from the other account's authenticator app.">
      <input className="desk-input min-h-11" inputMode="numeric" autoComplete="off" maxLength={10} value={fields.otp}
        onChange={event => set("otp", digits(event.target.value))} />
    </Field>
  </div>;
  return <div className="grid gap-4">
    <p className="text-sm text-muted">If <strong className="text-ink">{identifier}</strong> is an account we can link, we've emailed it a code, and sent a second code to this account's email. Codes expire quickly.</p>
    <Field label="Code sent to this account's email">
      <input className="desk-input min-h-11" inputMode="numeric" autoComplete="one-time-code" maxLength={12} value={fields.survivorCode}
        onChange={event => set("survivorCode", digits(event.target.value))} />
    </Field>
    <Field label="Code sent to the other account's email">
      <input className="desk-input min-h-11" inputMode="numeric" autoComplete="off" maxLength={12} value={fields.sourceCode}
        onChange={event => set("sourceCode", digits(event.target.value))} />
    </Field>
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" className="desk-button min-h-11" disabled={resending} aria-busy={resending || undefined} onClick={onResend}>
        {resending ? "Sending…" : "Send new codes"}</button>
      {resent ? <p role="status" className="text-sm text-muted">New codes sent. Earlier codes no longer work.</p> : null}
    </div>
  </div>;
}

export const proofReady = (method: MergeMethod, fields: ProofFields) => method === "credentials"
  ? Boolean(fields.password && fields.otp.length >= 6) : Boolean(fields.survivorCode && fields.sourceCode);
