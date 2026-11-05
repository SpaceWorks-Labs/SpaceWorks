import { useState, type FormEvent } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "../platformSpaces/ActionDialog";
import { fieldError } from "./parityRequest";
import { useCreateOidcProvider, type OidcProviderBody } from "./ssoApi";

const EMPTY: OidcProviderBody = { slug: "", display_name: "", issuer: "", jwks_url: "", client_id: "", is_enabled: true, allow_auto_link: true };
const FIELDS = ["slug", "display_name", "issuer", "jwks_url", "client_id"] as const;
const SLUG = /^[-a-zA-Z0-9_]+$/;
type TextField = (typeof FIELDS)[number];
const https = (value: string) => !value.trim() || value.trim().startsWith("https://");

/** Add an OpenID Connect provider (Keycloak, Authentik, Azure AD, Okta…). */
export function SsoProviderForm() {
  const create = useCreateOidcProvider();
  const [form, setForm] = useState(EMPTY);
  const set = <K extends keyof OidcProviderBody>(key: K, value: OidcProviderBody[K]) => setForm(current => ({ ...current, [key]: value }));
  const local: Partial<Record<TextField, string>> = {
    slug: form.slug && !SLUG.test(form.slug) ? "Use letters, digits, - and _ only." : undefined,
    issuer: https(form.issuer) ? undefined : "The issuer must start with https://.",
    jwks_url: https(form.jwks_url) ? undefined : "The key set address must start with https://.",
  };
  const errorFor = (name: TextField) => local[name] ?? fieldError(create.error, name);
  const valid = FIELDS.every(name => form[name].trim()) && !Object.values(local).some(Boolean);
  const general = create.error && !FIELDS.some(name => fieldError(create.error, name)) ? actionErrorText(create.error) : "";
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || create.isPending) return;
    const body = { ...form };
    for (const name of FIELDS) body[name] = form[name].trim();
    create.mutate(body, { onSuccess: () => { toast("Provider added."); setForm(EMPTY); } });
  };
  const text = (name: TextField, label: string, hint?: string, max = 255) => <Field label={label} hint={hint} error={errorFor(name)}>
    <input className="desk-input" value={form[name]} maxLength={max} spellCheck={false} onChange={event => set(name, event.target.value)} />
  </Field>;
  return <form className="grid gap-4 p-3" aria-label="New sign-on provider" onSubmit={submit} noValidate>
    <div className="grid gap-4 sm:grid-cols-2">
      {text("display_name", "Name on the sign-in button", undefined, 80)}
      {text("slug", "Short name", "Letters, digits, - and _ only. Linked sign-ins are stored under it.", 40)}
      {text("issuer", "Issuer", "Exactly as the provider issues it, trailing slash included.")}
      {text("jwks_url", "Key set address (JWKS)")}
      {text("client_id", "Client ID", "This deployment's client ID at the provider.")}
    </div>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={form.is_enabled} onChange={event => set("is_enabled", event.target.checked)} />Turn it on now
    </label>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={form.allow_auto_link} onChange={event => set("allow_auto_link", event.target.checked)} />
      Link a first sign-in to an existing account when both emails are verified
    </label>
    {general ? <p role="alert" className="text-sm text-danger">{general}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!valid || create.isPending}>
      {create.isPending ? "Adding…" : "Add provider"}
    </button>
  </form>;
}
