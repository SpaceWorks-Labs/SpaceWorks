import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field, SegmentedControl } from "../../components/ui";
import { fileToBase64, type WalletCredentialsInput } from "./api";

type Submit = (input: WalletCredentialsInput) => void;
const readText = (file: File | undefined, done: (text: string) => void) => { if (file) void file.text().then(done); };

/** Apple: Pass Type ID and Team ID, then either the .p12 export or the PEM certificate, key and WWDR. */
export function AppleCredentialForm({ pending, onSubmit }: { pending: boolean; onSubmit: Submit }) {
  const [method, setMethod] = useState<"p12" | "pem">("p12");
  const [ids, setIds] = useState({ apple_pass_type_id: "", apple_team_id: "" });
  const [p12, setP12] = useState({ apple_p12: "", apple_p12_password: "" });
  const [pem, setPem] = useState({ apple_cert_pem: "", apple_key_pem: "", apple_key_passphrase: "", apple_wwdr_pem: "" });
  const ready = ids.apple_pass_type_id.trim() && ids.apple_team_id.trim()
    && (method === "p12" ? Boolean(p12.apple_p12) : Boolean(pem.apple_cert_pem.trim() && pem.apple_key_pem.trim() && pem.apple_wwdr_pem.trim()));
  const area = (field: keyof typeof pem, label: string) => <Field label={label}>
    <textarea className="desk-input min-h-24 font-mono text-xs" spellCheck={false} autoComplete="off" value={pem[field]} onChange={(event) => setPem({ ...pem, [field]: event.target.value })} /></Field>;
  return <form className="grid gap-3" aria-label={t`Apple Wallet credentials`} onSubmit={(event) => {
    event.preventDefault();
    if (ready) onSubmit({ ...ids, ...(method === "p12" ? p12 : pem) });
  }}>
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t`Pass Type ID`} hint={t`For example pass.org.example.member.`}><input className="desk-input" autoComplete="off" value={ids.apple_pass_type_id} onChange={(event) => setIds({ ...ids, apple_pass_type_id: event.target.value })} /></Field>
      <Field label={t`Team ID`}><input className="desk-input" autoComplete="off" value={ids.apple_team_id} onChange={(event) => setIds({ ...ids, apple_team_id: event.target.value })} /></Field>
    </div>
    <p className="text-sm text-muted">{t`Changing the Pass Type ID starts a new pass type. Passes already in members' wallets won't update; holders re-add them from My passes.`}</p>
    <SegmentedControl label={t`Certificate format`} value={method} onChange={(value) => setMethod(value as "p12" | "pem")}
      options={[{ value: "p12", label: t`.p12 file` }, { value: "pem", label: t`PEM text` }]} />
    {method === "p12" ? <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t`Pass Type ID certificate (.p12)`}><input className="desk-input" type="file" accept=".p12,.pfx,application/x-pkcs12"
        onChange={(event) => { const file = event.target.files?.[0]; if (file) void fileToBase64(file).then((value) => setP12((state) => ({ ...state, apple_p12: value }))); }} /></Field>
      <Field label={t`.p12 password`}><input className="desk-input" type="password" autoComplete="new-password" value={p12.apple_p12_password} onChange={(event) => setP12({ ...p12, apple_p12_password: event.target.value })} /></Field>
    </div> : <div className="grid gap-3">
      {area("apple_cert_pem", t`Certificate (PEM)`)}{area("apple_key_pem", t`Private key (PEM)`)}
      <Field label={t`Key passphrase (if any)`}><input className="desk-input" type="password" autoComplete="new-password" value={pem.apple_key_passphrase} onChange={(event) => setPem({ ...pem, apple_key_passphrase: event.target.value })} /></Field>
      {area("apple_wwdr_pem", t`Apple WWDR intermediate certificate (PEM)`)}
    </div>}
    <div><button type="submit" className="desk-button-primary min-h-11" disabled={!ready || pending}>{pending ? t`Saving…` : t`Save Apple credentials`}</button></div>
  </form>;
}

/** Google: issuer ID, class prefix and the service-account JSON key. */
export function GoogleCredentialForm({ pending, onSubmit }: { pending: boolean; onSubmit: Submit }) {
  const [form, setForm] = useState({ google_issuer_id: "", google_class_prefix: "", google_service_account: "" });
  const ready = form.google_issuer_id.trim() && form.google_service_account.trim();
  return <form className="grid gap-3" aria-label={t`Google Wallet credentials`} onSubmit={(event) => { event.preventDefault(); if (ready) onSubmit(form); }}>
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t`Issuer ID`}><input className="desk-input" inputMode="numeric" autoComplete="off" value={form.google_issuer_id} onChange={(event) => setForm({ ...form, google_issuer_id: event.target.value })} /></Field>
      <Field label={t`Class prefix (optional)`}><input className="desk-input" autoComplete="off" value={form.google_class_prefix} onChange={(event) => setForm({ ...form, google_class_prefix: event.target.value })} /></Field>
    </div>
    <Field label={t`Service-account key file (JSON)`}><input className="desk-input" type="file" accept=".json,application/json"
      onChange={(event) => readText(event.target.files?.[0], (text) => setForm((state) => ({ ...state, google_service_account: text })))} /></Field>
    {form.google_service_account ? <p className="text-sm text-muted">{t`Key file loaded. It is sent once and never shown again.`}</p> : null}
    <div><button type="submit" className="desk-button-primary min-h-11" disabled={!ready || pending}>{pending ? t`Saving…` : t`Save Google credentials`}</button></div>
  </form>;
}
