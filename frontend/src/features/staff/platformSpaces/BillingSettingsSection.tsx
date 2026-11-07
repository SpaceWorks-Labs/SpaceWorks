import { t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { ErrorText, Field, Skeleton, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { useBillingSettings, useSaveBillingSettings, type BillingSettings } from "./plansApi";

const SECRETS = [
  ["stripe_secret_key", "Stripe secret key", "stripe"], ["stripe_webhook_secret", "Stripe webhook secret", "stripe"],
  ["razorpay_key_secret", "Razorpay key secret", "razorpay"], ["razorpay_webhook_secret", "Razorpay webhook secret", "razorpay"],
] as const;

function BillingForm({ data }: { data: BillingSettings }) {
  const save = useSaveBillingSettings();
  const [auto, setAuto] = useState(data.auto_enforce_enabled);
  const [grace, setGrace] = useState(String(data.grace_days));
  const [provider, setProvider] = useState(data.provider);
  const [keyId, setKeyId] = useState(data.razorpay_key_id);
  // Write-only: a secret is sent only when typed here ("" would clear it, so blank fields are left out).
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const valid = Number.isInteger(Number(grace)) && Number(grace) >= 0;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid || save.isPending) return;
    const typed = Object.fromEntries(Object.entries(secrets).filter(([, value]) => value.trim() !== ""));
    save.mutate({ auto_enforce_enabled: auto, grace_days: Number(grace), provider, razorpay_key_id: keyId.trim(), ...typed },
      { onSuccess: () => { setSecrets({}); toast(t`Billing settings saved.`); } });
  };
  return <form className="grid gap-4" aria-label={t`Billing settings`} onSubmit={submit} noValidate>
    <p className="flex flex-wrap items-center gap-2 text-sm text-ink">{t`Online billing switch (set on the server):`}<StatusPill label={data.online_billing_switch ? t`On` : t`Off`} tone={data.online_billing_switch ? "success" : "neutral"} /></p>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={auto} onChange={event => setAuto(event.target.checked)} />{t`Make a space read-only when its trial ends or an invoice is overdue`}</label>
    <Field label={t`Grace days after the due date`} className="max-w-xs">
      <input className="desk-input" type="number" min={0} value={grace} onChange={event => setGrace(event.target.value)} />
    </Field>
    <Field label={t`Payment provider`} className="max-w-xs">
      <select className="desk-input" value={provider} onChange={event => setProvider(event.target.value as BillingSettings["provider"])}>
        <option value="">{t`None`}</option><option value="stripe">{t`Stripe`}</option><option value="razorpay">{t`Razorpay`}</option>
      </select>
    </Field>
    {provider === "razorpay" ? <Field label={t`Razorpay key ID`} className="max-w-md">
      <input className="desk-input" autoComplete="off" value={keyId} onChange={event => setKeyId(event.target.value)} />
    </Field> : null}
    {SECRETS.filter(([, , owner]) => owner === provider).map(([key, label]) => <Field key={key} label={label} className="max-w-md"
      hint={data[`${key}_set` as keyof BillingSettings] ? t`Saved. Type a new value to replace it.` : t`Not set.`}>
      <input className="desk-input" type="password" autoComplete="new-password" value={secrets[key] ?? ""}
        onChange={event => setSecrets(current => ({ ...current, [key]: event.target.value }))} />
    </Field>)}
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
    <button type="submit" className="desk-button-primary w-full sm:w-fit" disabled={!valid || save.isPending}>{save.isPending ? t`Saving…` : t`Save billing settings`}</button>
  </form>;
}

export function BillingSettingsSection() {
  const settings = useBillingSettings();
  if (settings.isLoading) return <Skeleton className="h-24 w-full" />;
  if (settings.isError || !settings.data) return <ErrorText resource="billing settings" onRetry={() => { void settings.refetch(); }} />;
  return <BillingForm key={settings.data.updated_at} data={settings.data} />;
}
