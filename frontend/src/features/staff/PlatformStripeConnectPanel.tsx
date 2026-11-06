import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog, SettingsRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { PlatformConfigurationSection } from "./PlatformConfigurationSection";
import { useStaffGet } from "./StaffPanels";
type PlatformPaymentSettings = {
  id: number;
  stripe_publishable_key_set: boolean;
  stripe_secret_key_set: boolean;
  stripe_webhook_secret_set: boolean;
  stripe_connect_client_id: string;
  application_fee_bps: number;
  updated_at: string;
};
type RevocableCredential =
  | "stripe_publishable_key"
  | "stripe_secret_key"
  | "stripe_webhook_secret";

export function PlatformStripeConnectPanel({ embedded = false }: { embedded?: boolean }) {
  const queryClient = useQueryClient();
  const settings = useStaffGet<PlatformPaymentSettings>(
    ["platform-payment-settings"],
    "/admin/platform/payment-settings",
  );
  const [confirm, setConfirm] = useState<RevocableCredential | null>(null);
  const [publishableKey, setPublishableKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [clientId, setClientId] = useState("");
  const [feeBps, setFeeBps] = useState("0");
  useEffect(() => {
    if (!settings.data) return;
    setClientId(settings.data.stripe_connect_client_id ?? "");
    setFeeBps(String(settings.data.application_fee_bps ?? 0));
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () =>
      staffRequest<PlatformPaymentSettings>("/admin/platform/payment-settings", {
        method: "PATCH",
        body: JSON.stringify({
          stripe_connect_client_id: clientId,
          application_fee_bps: Number(feeBps) || 0,
          ...(publishableKey ? { stripe_publishable_key: publishableKey } : {}),
          ...(secretKey ? { stripe_secret_key: secretKey } : {}),
          ...(webhookSecret ? { stripe_webhook_secret: webhookSecret } : {}),
        }),
      }),
    onSuccess: () => {
      setPublishableKey("");
      setSecretKey("");
      setWebhookSecret("");
      queryClient.invalidateQueries({ queryKey: ["platform-payment-settings"] });
    },
  });
  const clearCredential = useMutation({
    mutationFn: (credential: RevocableCredential) =>
      staffRequest<PlatformPaymentSettings>("/admin/platform/payment-settings", {
        method: "PATCH",
        body: JSON.stringify({ [credential]: "" }),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["platform-payment-settings"] }),
  });
  const busy = settings.isLoading || save.isPending || clearCredential.isPending;
  const dirty = Boolean(publishableKey || secretKey || webhookSecret || clientId !== (settings.data?.stripe_connect_client_id ?? "") || feeBps !== String(settings.data?.application_fee_bps ?? 0));
  const credentials: { key: RevocableCredential; label: string; saved: boolean }[] = [
    { key: "stripe_publishable_key", label: t`Clear publishable key`, saved: Boolean(settings.data?.stripe_publishable_key_set) },
    { key: "stripe_secret_key", label: t`Clear secret key`, saved: Boolean(settings.data?.stripe_secret_key_set) },
    { key: "stripe_webhook_secret", label: t`Clear webhook secret`, saved: Boolean(settings.data?.stripe_webhook_secret_set) },
  ];
  return <><PlatformConfigurationSection title={t`Platform Stripe Connect`} subtitle={t`Platform credentials authorize direct charges into each space’s connected account.`} embedded={embedded}
    state={{ status: settings.isLoading ? "loading" : settings.error ? "error" : "ready", error: "Couldn't load Stripe Connect settings. Try again.", onRetry: () => { void settings.refetch(); } }}
    save={{ dirty, pending: save.isPending, disabled: busy, error: (save.error ?? clearCredential.error)?.message,
      onSave: () => save.mutate(), onDiscard: () => { save.reset(); clearCredential.reset(); setPublishableKey(""); setSecretKey(""); setWebhookSecret(""); setClientId(settings.data?.stripe_connect_client_id ?? ""); setFeeBps(String(settings.data?.application_fee_bps ?? 0)); } }}
    danger={credentials.map(item => ({ title: item.label, consequence: "Removes the saved credential. Connected payment services may stop working.",
      action: { label: item.label, disabled: !item.saved || busy, disabledReason: !item.saved ? "No saved credential." : undefined, onClick: () => setConfirm(item.key) } }))}>
    <StatusPill label={settings.data?.stripe_secret_key_set && settings.data.stripe_connect_client_id.trim() ? t`Connect credentials configured` : t`Not configured`} />
    <div className="divide-y divide-line">
          <SettingsRow label={t`Platform publishable key`}><input aria-label={t`Platform publishable key`} className="desk-input w-full" type="password" autoComplete="new-password" placeholder={settings.data?.stripe_publishable_key_set ? t`Platform publishable key set` : undefined} value={publishableKey} onChange={(event) => setPublishableKey(event.target.value)} /></SettingsRow>
          <SettingsRow label={t`Platform secret key`}><input aria-label={t`Platform secret key`} className="desk-input w-full" type="password" autoComplete="new-password" placeholder={settings.data?.stripe_secret_key_set ? t`Platform secret key set` : undefined} value={secretKey} onChange={(event) => setSecretKey(event.target.value)} /></SettingsRow>
          <SettingsRow label={t`Platform webhook secret`}><input aria-label={t`Platform webhook secret`} className="desk-input w-full" type="password" autoComplete="new-password" placeholder={settings.data?.stripe_webhook_secret_set ? t`Platform webhook secret set` : undefined} value={webhookSecret} onChange={(event) => setWebhookSecret(event.target.value)} /></SettingsRow>
          <SettingsRow label={t`Stripe Connect client ID`}><input aria-label={t`Stripe Connect client ID`} className="desk-input w-full" value={clientId} onChange={(event) => setClientId(event.target.value)} /></SettingsRow>
          <input
            aria-label={t`Application fee basis points`}
            className="desk-input"
            inputMode="numeric"
            min={0}
            max={10000}
            type="number"
            value={feeBps}
            onChange={(event) => setFeeBps(event.target.value)}
          />
    </div>
    <p className="text-sm text-muted">{t`Application fee: ${settings.data?.application_fee_bps ?? 0} basis points. 100 = 1%. Saved keys are never returned.`}</p>
  </PlatformConfigurationSection>
  <ConfirmDialog open={confirm !== null} title={t`Clear platform credential?`} message={t`Connected payment services using this credential may stop working.`}
    confirmLabel={t`Clear credential`} tone="danger" pending={clearCredential.isPending} onCancel={() => setConfirm(null)}
    onConfirm={() => { if (confirm) clearCredential.mutate(confirm); setConfirm(null); }} />
  </>;
}
