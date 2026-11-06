import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { useSaveNativeApp, type NativeApp, type NativeAppBody } from "./nativeAppsApi";
import { fieldError } from "./parityRequest";

const EMPTY: NativeAppBody = { makerspace: null, app_id: "", platform: "android", environment: "production", verifier_config_key: "",
  signing_identities: [], min_supported_version: null, status: "pending" };
const FIELDS = ["app_id", "platform", "environment", "verifier_config_key", "signing_identities", "min_supported_version", "status"];

/** Register an app identity, or change one when `row` is given. The server checks the id and signer format. */
export function NativeAppForm({ row, onDone }: { row?: NativeApp; onDone?: () => void }) {
  const save = useSaveNativeApp(row?.id ?? null);
  const [form, setForm] = useState<NativeAppBody>(row ? { makerspace: row.makerspace, app_id: row.app_id, platform: row.platform,
    environment: row.environment, verifier_config_key: row.verifier_config_key, signing_identities: row.signing_identities,
    min_supported_version: row.min_supported_version, status: row.status } : EMPTY);
  const [signers, setSigners] = useState((row?.signing_identities ?? []).join("\n"));
  const set = <K extends keyof NativeAppBody>(name: K, value: NativeAppBody[K]) => setForm(current => ({ ...current, [name]: value }));
  const valid = form.app_id.trim() && form.verifier_config_key.trim() && signers.trim();
  const general = save.error && !FIELDS.some(name => fieldError(save.error, name)) ? actionErrorText(save.error) : "";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || save.isPending) return;
    save.mutate({ ...form, app_id: form.app_id.trim(), min_supported_version: form.min_supported_version?.trim() || null,
      signing_identities: signers.split(/\s+/).filter(Boolean) }, { onSuccess: () => {
      toast(row ? "App saved." : "App registered.");
      if (!row) { setForm(EMPTY); setSigners(""); }
      onDone?.();
    } });
  };
  const select = (name: "platform" | "environment" | "status", options: [string, string][]) =>
    <select className="desk-input" value={form[name]} onChange={event => set(name, event.target.value as never)}>
      {options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>;
  return <form className="grid gap-4 p-3" aria-label={row ? `Edit ${row.app_id}` : "Register an app"} onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Package or bundle ID" error={fieldError(save.error, "app_id")}>
        <input className="desk-input" value={form.app_id} spellCheck={false} autoComplete="off" onChange={event => set("app_id", event.target.value)} />
      </Field>
      <Field label="Verifier name" hint="The attestation setup this app uses." error={fieldError(save.error, "verifier_config_key")}>
        <input className="desk-input" value={form.verifier_config_key} spellCheck={false} onChange={event => set("verifier_config_key", event.target.value)} />
      </Field>
      <Field label="Platform" error={fieldError(save.error, "platform")}>{select("platform", [["android", "Android"], ["apple", "Apple"]])}</Field>
      <Field label="Environment" error={fieldError(save.error, "environment")}>
        {select("environment", [["production", "Production"], ["development", "Development"]])}</Field>
      <Field label="Status" hint="Revoking ends every sign-in this app issued." error={fieldError(save.error, "status")}>
        {select("status", [["pending", "Pending"], ["approved", "Approved"], ["revoked", "Revoked"]])}</Field>
      <Field label="Oldest supported version" hint="For example 1.4.0. Blank for any." error={fieldError(save.error, "min_supported_version")}>
        <input className="desk-input" value={form.min_supported_version ?? ""} onChange={event => set("min_supported_version", event.target.value)} />
      </Field>
    </div>
    <Field label="Signer digests or App ID Prefix" hint="One per line. Android: 1 to 5 SHA-256 distribution digests (never the upload key). Apple: exactly one App ID Prefix."
      error={fieldError(save.error, "signing_identities")}>
      <textarea className="desk-input min-h-24 font-mono" value={signers} spellCheck={false} onChange={event => setSigners(event.target.value)} />
    </Field>
    {fieldError(save.error, "non_field_errors") ? <p role="alert" className="text-sm text-danger">{fieldError(save.error, "non_field_errors")}</p> : null}
    {general ? <p role="alert" className="text-sm text-danger">{general}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!valid || save.isPending}>
        {save.isPending ? "Saving…" : row ? "Save app" : "Register app"}</button>
      {row ? <button type="button" className="desk-button w-full sm:w-fit" disabled={save.isPending} onClick={onDone}>Cancel</button> : null}
    </div>
  </form>;
}
