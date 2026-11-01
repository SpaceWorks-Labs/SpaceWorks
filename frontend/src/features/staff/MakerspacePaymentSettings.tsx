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

export function MakerspacePaymentSettings({ makerspace }: { makerspace: Makerspace }) {
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
  const loans = featureEnabled(makerspace.enabled_features ?? [], "charges.loans")
    ? <MakerspaceLoanSettings makerspaceId={makerspace.id} pricingOn={capabilityOn(makerspace, "charges.pricing")} /> : null;
  if ((settings.error as { status?: number } | null)?.status === 404) return loans;

  return <>
    <SettingsQueryState query={settings} resource="payment">
      <SettingsRow label="Online payments" helper="Choose one provider for this makerspace. Saved credentials are encrypted and never displayed again. Credential changes require recent identity verification.">
        <div className="@container grid min-w-0 gap-4">
          <StatusPill label={settings.data?.effective_mode === "raw" ? "Own credentials"
            : settings.data?.effective_mode === "connect" ? "Stripe Connect" : "Unavailable"}
            tone={settings.data?.effective_mode === "unavailable" ? "neutral" : "success"} />
          <Field label="Payment provider">
            <select className="desk-input" value={provider} disabled={busy}
              onChange={(event) => { setProvider(event.target.value as Provider); setDraft({}); }}>
              <option value="stripe">Stripe</option>
              <option value="razorpay">Razorpay</option>
            </select>
          </Field>
          <p className="text-sm text-muted">Settle or close pending online collections before switching providers.</p>
          <PaymentCredentialFields provider={provider} settings={settings.data} draft={draft}
            onChange={setDraft} disabled={busy} />
          <Field label="Default payment currency">
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
              <p className="font-semibold text-ink">Stripe Connect</p>
              <p className="text-sm text-muted">Status: {settings.data?.connect_status ?? "unconnected"}</p>
              <button className="desk-button-primary mt-2" disabled={busy || dirty} onClick={() => onboard.mutate()}>
                {settings.data?.connect_status === "unconnected" ? "Connect Stripe" : "Reconnect Stripe"}
              </button>
              <p className="mt-2 text-sm text-muted">Own Stripe credentials take precedence. Clearing them restores an available Connect account.</p>
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
