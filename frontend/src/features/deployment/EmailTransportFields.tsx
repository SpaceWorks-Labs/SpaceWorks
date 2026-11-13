import { t } from "@lingui/core/macro";
import { Field } from "../../components/ui";
import { EMAIL_PROVIDERS, PROVIDER_FIELDS, optionalProviderFields, type EmailForm, type EmailProvider } from "./emailSettings";

const LABELS: Record<string, string> = {
  api_key: t`API key`, server_token: t`Server token`, domain: t`Sending domain`, region: t`Region`,
  access_key_id: t`Dedicated AWS access key ID`, secret_access_key: t`Dedicated AWS secret access key`,
  session_token: t`AWS session token (optional)`,
  account_key: t`Shared provider account alias (optional)`, webhook_secret: t`Webhook secret (optional)`,
  webhook_signing_key: t`Webhook signing key (optional)`,
};
export function EmailTransportFields({ form, onChange, platform, disabled, configured, passwordSet }: {
  form: EmailForm; onChange: (form: EmailForm) => void; platform: boolean; disabled: boolean;
  configured?: boolean; passwordSet?: boolean;
}) {
  return <fieldset disabled={disabled} className="grid min-w-0 gap-4">
    <legend className="sr-only">{t`Email transport`}</legend>
    <Field label={t`Email provider`}><select className="desk-input" value={form.provider}
      onChange={event => onChange({ ...form, provider: event.target.value as EmailProvider, credentials: {}, password: "" })}>
      {EMAIL_PROVIDERS.map(provider => <option key={provider} value={provider}>
        {provider === "inherit" ? platform ? t`Use deployment environment` : t`Inherit platform email` : provider === "smtp" ? "SMTP" : provider === "ses" ? t`Amazon SES (HTTP)` : `${provider[0].toUpperCase()}${provider.slice(1)} (HTTP)`}
      </option>)}
    </select></Field>
    <p className="text-sm text-muted">{platform ? t`Password resets and authentication mail always use platform configuration.` : t`Makerspace notifications use this sender. Platform authentication mail remains separate.`} {t` A broken explicit transport fails without switching provider.`}</p>
    {form.provider !== "inherit" ? <Field label={t`From email`} hint={t`Use a sender verified with the selected provider.`}>
      <input className="desk-input" value={form.sender} onChange={event => onChange({ ...form, sender: event.target.value })} />
    </Field> : null}
    {form.provider === "smtp" ? <>
      <div className="grid gap-4 @md:grid-cols-2">
        <Field label={t`SMTP host`}><input className="desk-input" value={form.host} onChange={event => onChange({ ...form, host: event.target.value })} /></Field>
        <Field label={t`SMTP port`}><input className="desk-input" inputMode="numeric" value={form.port} onChange={event => onChange({ ...form, port: event.target.value })} /></Field>
        <Field label={t`SMTP username`}><input className="desk-input" autoComplete="off" value={form.username} onChange={event => onChange({ ...form, username: event.target.value })} /></Field>
        <Field label={t`SMTP password`} hint={passwordSet ? t`Password set. Leave blank to keep it.` : t`No password saved.`}>
          <input className="desk-input" type="password" autoComplete="new-password" value={form.password} onChange={event => onChange({ ...form, password: event.target.value })} />
        </Field>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.tls}
        onChange={event => onChange({ ...form, tls: event.target.checked, ssl: event.target.checked ? false : form.ssl })} />{t`Use STARTTLS (587)`}</label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={form.ssl}
        onChange={event => onChange({ ...form, ssl: event.target.checked, tls: event.target.checked ? false : form.tls })} />{t`Use implicit SSL (465)`}</label>
    </> : form.provider !== "inherit" ? <>
      <p className="text-sm text-muted">{configured ? t`Provider configuration saved. Leave fields blank to keep it; enter all required fields to replace it. Re-enter any account alias and webhook settings too.` : t`Enter the provider configuration.`} {t` Secrets are write-only. Your platform operator sets the free-account sending budget.`}</p>
      {form.provider === "ses" ? <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox"
        checked={form.credentials.workload_identity === true} onChange={event => onChange({ ...form, credentials: { workload_identity: event.target.checked } })} />{t`Use dedicated workload identity for SES`}</label> : null}
      {[...PROVIDER_FIELDS[form.provider], ...optionalProviderFields(form.provider)].filter(key => !(form.provider === "ses" && form.credentials.workload_identity
        && ["access_key_id", "secret_access_key", "session_token"].includes(key))).map(key => <Field key={key} label={LABELS[key]}
          hint={key === "region" && form.provider === "mailgun" ? t`Enter us or eu.` : undefined}>
        <input className="desk-input" type={["region", "domain"].includes(key) ? "text" : "password"} autoComplete="off"
          value={String(form.credentials[key] ?? "")} onChange={event => onChange({ ...form, credentials: { ...form.credentials, [key]: event.target.value } })} />
      </Field>)}
    </> : null}
  </fieldset>;
}
