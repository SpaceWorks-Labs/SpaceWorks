import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../components/ui";

export type Provider = "stripe" | "razorpay";
const credentials = {
  stripe: [
    ["stripe_publishable_key", "Stripe publishable key"],
    ["stripe_secret_key", "Stripe secret key"],
    ["stripe_webhook_secret", "Stripe webhook secret"],
  ],
  razorpay: [
    ["razorpay_key_id", "Razorpay key ID"],
    ["razorpay_key_secret", "Razorpay API key secret"],
    ["razorpay_webhook_secret", "Razorpay webhook secret"],
  ],
} as const;
type Credential = (typeof credentials)[Provider][number][0];
export type CredentialDraft = Partial<Record<Credential, string>>;
export type PaymentSettings = Record<`${Credential}_set`, boolean> & {
  provider: Provider;
  default_currency: string;
  effective_mode: "raw" | "connect" | "unavailable";
  stripe_webhook_url: string;
  razorpay_webhook_url: string;
  connect_status: "unconnected" | "pending" | "active" | "restricted" | "disconnected";
};

export function PaymentCredentialFields({ provider, settings, draft, onChange, disabled }: {
  provider: Provider; settings?: PaymentSettings; draft: CredentialDraft;
  onChange: (value: CredentialDraft) => void; disabled: boolean;
}) {
  const change = (field: Credential, value?: string) => {
    const next = { ...draft };
    if (value === undefined) delete next[field];
    else next[field] = value;
    onChange(next);
  };
  return <>
    <div className="grid gap-4 @md:grid-cols-2">
      {credentials[provider].map(([field, label]) => {
        const saved = Boolean(settings?.[`${field}_set`]);
        const clearing = draft[field] === "";
        return <div key={field} className="min-w-0">
          <Field label={label}>
            <input className="desk-input" type="password" autoComplete="new-password"
              maxLength={255} value={draft[field] ?? ""} disabled={disabled || clearing}
              placeholder={saved ? `${label} set` : t`Not set`}
              onChange={(event) => change(field, event.target.value || undefined)} />
          </Field>
          <p className="text-sm text-muted">{clearing ? t`Will clear on save` : saved ? t`Saved value set` : t`No saved value`}</p>
          {saved ? <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={clearing} disabled={disabled}
              onChange={(event) => change(field, event.target.checked ? "" : undefined)} />
            {t`Clear saved ${label}`}
          </label> : null}
        </div>;
      })}
    </div>
    <WebhookUrl label={t`Stripe webhook URL`} url={settings?.stripe_webhook_url} />
    <WebhookUrl label={t`Razorpay webhook URL`} url={settings?.razorpay_webhook_url} />
  </>;
}

function WebhookUrl({ label, url }: { label: string; url?: string }) {
  const [result, setResult] = useState("");
  return <div className="min-w-0">
    <Field label={label}><input className="desk-input w-full" readOnly value={url ?? ""} /></Field>
    <button type="button" className="desk-button-secondary mt-2" disabled={!url} onClick={async () => {
      try { await navigator.clipboard.writeText(url!); setResult("Copied"); }
      catch { setResult("Copy failed. Select and copy the URL above."); }
    }}>{t`Copy ${label}`}</button>
    <span role="status" className="ml-2 text-sm text-muted">{result}</span>
  </div>;
}
