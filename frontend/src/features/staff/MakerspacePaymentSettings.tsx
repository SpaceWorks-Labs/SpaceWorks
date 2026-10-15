import { SettingsResetAction } from "./SettingsResetAction";
import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge, Field } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { featureEnabled } from "../../lib/features";
import { MakerspaceLoanSettings } from "./MakerspaceLoanSettings";
import { type Makerspace, useStaffGet } from "./StaffPanels";

type PaymentSettings = {
  default_currency: string;
  stripe_publishable_key_set: boolean;
  stripe_secret_key_set: boolean;
  stripe_webhook_secret_set: boolean;
  effective_mode: "raw" | "connect" | "unavailable";
  connect_account_id?: string | null;
  connect_status: "unconnected" | "pending" | "active" | "restricted" | "disconnected";
  connect_charges_enabled: boolean;
  connect_payouts_enabled: boolean;
};

export function MakerspacePaymentSettings({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const queryKey = ["payment-settings", makerspace.id];
  const path = `/admin/makerspace/${makerspace.id}/payment-settings`;
  const settings = useStaffGet<PaymentSettings>(queryKey, path);
  const [publishableKey, setPublishableKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [currency, setCurrency] = useState("usd");

  useEffect(() => {
    if (settings.data) setCurrency(settings.data.default_currency);
  }, [settings.data]);

  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey }),
    // Both editors expose the same currency row; refresh its other reader too.
    queryClient.invalidateQueries({ queryKey: ["makerspace-profile", makerspace.id] }),
  ]);
  const save = useMutation({
    mutationFn: () =>
      staffRequest<PaymentSettings>(path, {
        method: "PATCH",
        body: JSON.stringify({
          default_currency: currency,
          ...(publishableKey ? { stripe_publishable_key: publishableKey } : {}),
          ...(secretKey ? { stripe_secret_key: secretKey } : {}),
          ...(webhookSecret ? { stripe_webhook_secret: webhookSecret } : {}),
        }),
      }),
    onSuccess: () => {
      setPublishableKey("");
      setSecretKey("");
      setWebhookSecret("");
      refresh();
    },
  });
  const clear = useMutation({
    mutationFn: () =>
      staffRequest<PaymentSettings>(path, {
        method: "PATCH",
        body: JSON.stringify({
          stripe_publishable_key: "",
          stripe_secret_key: "",
          stripe_webhook_secret: "",
        }),
      }),
    onSuccess: refresh,
  });
  const onboard = useMutation({
    mutationFn: () =>
      staffRequest<{ authorize_url: string }>(`${path}/connect/onboard`, {
        method: "POST",
      }),
    onSuccess: ({ authorize_url }) => window.location.assign(authorize_url),
  });
  const busy = settings.isLoading || save.isPending || clear.isPending || onboard.isPending;

  // Keyed on charge TRACKING, not the online rail, and rendered OUTSIDE the
  // payment-settings query: that endpoint is part of the separable `payments_rail`
  // and 404s when the rail is tombstoned, which is exactly the cash-only space that
  // still raises deposits and late fees and must be able to configure them.
  const loans = featureEnabled(makerspace.enabled_features ?? [], "charges.loans")
    ? <MakerspaceLoanSettings makerspaceId={makerspace.id} /> : null;
  // No rail installed: there is no Stripe configuration to show, only loan charges.
  if ((settings.error as { status?: number } | null)?.status === 404) return loans;

  return (
    <><SettingsQueryState query={settings} resource="payment"><SettingsRow label="Stripe payments" helper="Secret credentials are encrypted; saved keys are never displayed again."><div className="@container grid min-w-0 gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>


        </div>
        <Badge label="" tone={settings.data?.effective_mode === "unavailable" ? "neutral" : "success"}>
          {modeLabel(settings.data?.effective_mode)}
        </Badge>
      </div>
      <div className="mt-4 grid gap-2 @md:grid-cols-2">
        <Field label="Stripe publishable key">
          <input
            className="desk-input"
            type="password"
            autoComplete="new-password"
            placeholder={settings.data?.stripe_publishable_key_set ? "Stripe publishable key set" : undefined}
            value={publishableKey}
            onChange={(event) => setPublishableKey(event.target.value)}
          />
        </Field>
        <Field label="Stripe secret key">
          <input
            className="desk-input"
            type="password"
            autoComplete="new-password"
            placeholder={settings.data?.stripe_secret_key_set ? "Stripe secret key set" : undefined}
            value={secretKey}
            onChange={(event) => setSecretKey(event.target.value)}
          />
        </Field>
        <Field label="Stripe webhook secret">
          <input
            className="desk-input"
            type="password"
            autoComplete="new-password"
            placeholder={settings.data?.stripe_webhook_secret_set ? "Stripe webhook secret set" : undefined}
            value={webhookSecret}
            onChange={(event) => setWebhookSecret(event.target.value)}
          />
        </Field>
        <input
          aria-label="Default payment currency"
          className="desk-input"
          maxLength={3}
          value={currency}
          onChange={(event) => setCurrency(event.target.value.toLowerCase())}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <SettingsEditorActions dirty={Boolean(publishableKey || secretKey || webhookSecret || currency !== (settings.data?.default_currency ?? "usd"))} onDiscard={() => { setPublishableKey(""); setSecretKey(""); setWebhookSecret(""); setCurrency(settings.data?.default_currency ?? "usd"); }} pending={save.isPending} disabled={busy} onSave={() => save.mutate()} />

      </div>
      {makerspace.platform_hosting ? (
        <div className="mt-4 rounded-md border border-line bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="font-semibold text-ink">Stripe Connect</p>
              <p className="text-sm text-muted">Status: {settings.data?.connect_status ?? "unconnected"}</p>
            </div>
            <button className="desk-button-primary" disabled={busy} onClick={() => onboard.mutate()}>
              {settings.data?.connect_status === "unconnected" ? "Connect Stripe" : "Reconnect Stripe"}
            </button>
          </div>
          <p className="mt-2 text-sm text-muted">
            A complete raw credential pair takes precedence over Connect; clearing it restores the Connect fallback.
          </p>
        </div>
      ) : null}
      {settings.error || save.error || clear.error || onboard.error ? (
        <p className="mt-2 text-sm text-danger" role="alert">
          {(settings.error || save.error || clear.error || onboard.error)?.message}
        </p>
      ) : null}
    </div><SettingsResetAction label={"Clear raw configuration"} consequence="Remove the saved Stripe credentials. Online checkout will use an available Connect account, or stop until credentials are configured." pending={clear.isPending} disabled={busy
            || !(
              settings.data?.stripe_publishable_key_set
              || settings.data?.stripe_secret_key_set
              || settings.data?.stripe_webhook_secret_set
            )} onConfirm={() => clear.mutateAsync()} /></SettingsRow></SettingsQueryState>{loans}</>
  );
}

function modeLabel(mode?: PaymentSettings["effective_mode"]) {
  return mode === "raw" ? "Raw credentials" : mode === "connect" ? "Stripe Connect" : "Unavailable";
}
