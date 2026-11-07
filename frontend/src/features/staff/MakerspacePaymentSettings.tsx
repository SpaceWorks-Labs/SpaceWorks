import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, SettingsRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { capabilityOn, featureEnabled } from "../../lib/features";
import { MakerspaceLoanSettings } from "./MakerspaceLoanSettings";
import { PaymentCredentialFields, type CredentialDraft, type PaymentSettings, type Provider } from "./PaymentCredentialFields";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsQueryState } from "./SettingsQueryState";
import { type Makerspace, useStaffGet } from "./StaffPanels";
import { staffChargesOn } from "./useStaffChargesOn";

export function MakerspacePaymentSettings({ makerspace }: { makerspace: Makerspace }) {
  // #95: the provider and its credentials are the online rail, so without the `payments`
  // module only the loan rules show (the backend refuses rail writes with 404). Unknown
  // modules (an older payload) fail open, like the rest of the console.
  if (makerspace.enabled_modules !== undefined && !makerspace.enabled_modules.includes("payments")) {
    return staffChargesOn(makerspace, "loans")
      ? <MakerspaceLoanSettings makerspaceId={makerspace.id} pricingOn={capabilityOn(makerspace, "charges.pricing")} /> : null;
  }
  return <PaymentSettingsEditor key={makerspace.id} makerspace={makerspace} />;
}

function PaymentSettingsEditor({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const queryKey = ["payment-settings", makerspace.id];
  const path = `/admin/makerspace/${makerspace.id}/payment-settings`;
  const settings = useStaffGet<PaymentSettings>(queryKey, path);
  const [provider, setProvider] = useState<Provider>("stripe");
  const [draft, setDraft] = useState<CredentialDraft>({});
  const [currency, setCurrency] = useState("usd");

  useEffect(() => {
    if (settings.data) {
      setCurrency(settings.data.default_currency);
      setProvider(settings.data.provider);
    }
  }, [settings.data]);

  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey }),
    // Both editors expose the same currency; refresh its other reader too.
    queryClient.invalidateQueries({ queryKey: ["makerspace-profile", makerspace.id] }),
  ]);
  const save = useMutation({
    mutationFn: () => staffRequest<PaymentSettings>(path, {
      method: "PATCH",
      body: JSON.stringify({
        default_currency: currency,
        ...(provider !== settings.data?.provider ? { provider } : {}),
        ...draft,
      }),
    }),
    onSuccess: async () => { setDraft({}); await refresh(); },
  });
  const onboard = useMutation({
    mutationFn: () => staffRequest<{ authorize_url: string }>(`${path}/connect/onboard`, { method: "POST" }),
    onSuccess: ({ authorize_url }) => window.location.assign(authorize_url),
  });
  const busy = settings.isLoading || save.isPending || onboard.isPending;
  const dirty = Boolean(Object.keys(draft).length
    || provider !== (settings.data?.provider ?? "stripe")
    || currency !== (settings.data?.default_currency ?? "usd"));

  // Loan tracking remains available even when the online rail is tombstoned.
  // #184: loan fees exist only while BOTH the charges master switch and charges.loans are on.
  const loans = featureEnabled(makerspace.enabled_features ?? [], "charges.loans") && capabilityOn(makerspace, "charges.enabled")
    ? <MakerspaceLoanSettings makerspaceId={makerspace.id} pricingOn={capabilityOn(makerspace, "charges.pricing")} /> : null;
  if ((settings.error as { status?: number } | null)?.status === 404) return loans;

  return <>
    <SettingsQueryState query={settings} resource="payment">
      <SettingsRow label={t`Online payments`} helper={t`Choose one provider for this makerspace. Saved credentials are encrypted and never displayed again. Credential changes require recent identity verification.`}>
        <div className="@container grid min-w-0 gap-4">
          <StatusPill label={settings.data?.effective_mode === "raw" ? t`Own credentials`
            : settings.data?.effective_mode === "connect" ? t`Stripe Connect` : t`Unavailable`}
            tone={settings.data?.effective_mode === "unavailable" ? "neutral" : "success"} />
          <Field label={t`Payment provider`}>
            <select className="desk-input" value={provider} disabled={busy}
              onChange={(event) => { setProvider(event.target.value as Provider); setDraft({}); }}>
              <option value="stripe">{t`Stripe`}</option>
              <option value="razorpay">{t`Razorpay`}</option>
            </select>
          </Field>
          <p className="text-sm text-muted">{t`Settle or close pending online collections before switching providers.`}</p>
          <PaymentCredentialFields provider={provider} settings={settings.data} draft={draft}
            onChange={setDraft} disabled={busy} />
          <Field label={t`Default payment currency`}>
            <input className="desk-input" maxLength={3} value={currency} disabled={busy}
              onChange={(event) => setCurrency(event.target.value.toLowerCase())} />
          </Field>
          <SettingsEditorActions dirty={dirty} onDiscard={() => {
            setDraft({}); setCurrency(settings.data?.default_currency ?? "usd");
            setProvider(settings.data?.provider ?? "stripe");
            save.reset();
          }} pending={save.isPending} disabled={busy} onSave={() => save.mutate()} />
          {provider === "stripe" && makerspace.platform_hosting ? (
            <div className="rounded-md border border-line bg-surface p-3">
              <p className="font-semibold text-ink">{t`Stripe Connect`}</p>
              <p className="text-sm text-muted">{t`Status: ${settings.data?.connect_status ?? "unconnected"}`}</p>
              <button className="desk-button-primary mt-2" disabled={busy || dirty} onClick={() => onboard.mutate()}>
                {settings.data?.connect_status === "unconnected" ? t`Connect Stripe` : t`Reconnect Stripe`}
              </button>
              <p className="mt-2 text-sm text-muted">{t`Own Stripe credentials take precedence. Clearing them restores an available Connect account.`}</p>
            </div>
          ) : null}
          {settings.error || save.error || onboard.error ? (
            <p className="text-sm text-danger" role="alert">
              {(settings.error || save.error || onboard.error)?.message}
            </p>
          ) : null}
        </div>
      </SettingsRow>
    </SettingsQueryState>
    {loans}
  </>;
}
