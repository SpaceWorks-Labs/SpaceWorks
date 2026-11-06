import { t } from "@lingui/core/macro";
import { SettingsResetAction } from "./SettingsResetAction";
import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { type Makerspace, useStaffGet } from "./StaffPanels";

type ApiSettings = {
  slack_webhook_url_set: boolean;
  mattermost_webhook_url_set: boolean;
  discord_webhook_url_set: boolean;
};

type ProviderCardProps = {
  configured: boolean;
  label: string;
  makerspaceId: number;
  provider: "slack" | "mattermost" | "discord";
};

// Read webhook state under a dedicated cache key (same endpoint) so saving/clearing a
// webhook never invalidates the shared ["api-settings", id] query that the SMTP form and
// its unsaved edits depend on. The notification channel matrix reads the same key, so its
// configuration warnings still refresh immediately after a webhook is saved.
export const DELIVERY_SETTINGS_KEY = (makerspaceId: number) => [
  "api-settings",
  makerspaceId,
  "delivery",
];

export function MakerspaceWebhookSettings({ makerspace }: { makerspace: Makerspace }) {
  const settings = useStaffGet<ApiSettings>(
    DELIVERY_SETTINGS_KEY(makerspace.id),
    `/admin/makerspace/${makerspace.id}/api-settings`,
  );

  return (
    <SettingsQueryState query={settings} resource="webhook"><SettingsRow label={t`Chat webhooks`} helper={t`Add incoming webhook URLs for Slack, Mattermost or Discord. Saving a webhook configures the destination; enable delivery separately in the notification channel matrix under Notifications. Each channel is also its own module, so a space ships only the ones it uses.`}><div className="@container grid min-w-0 gap-4">
      <div className="grid max-w-2xl gap-2">


      </div>
      <div className="mt-4 grid gap-3 @3xl:grid-cols-3">
        <ProviderCard
          configured={settings.data?.slack_webhook_url_set ?? false}
          label={t`Slack`}
          makerspaceId={makerspace.id}
          provider="slack"
        />
        <ProviderCard
          configured={settings.data?.mattermost_webhook_url_set ?? false}
          label={t`Mattermost`}
          makerspaceId={makerspace.id}
          provider="mattermost"
        />
        <ProviderCard
          configured={settings.data?.discord_webhook_url_set ?? false}
          label={t`Discord`}
          makerspaceId={makerspace.id}
          provider="discord"
        />
      </div>
      {settings.isLoading ? (
        <p className="mt-3 text-sm text-muted">{t`Loading webhook settings…`}</p>
      ) : null}
      {settings.error ? (
        <p className="mt-3 text-sm text-danger">{settings.error.message}</p>
      ) : null}
    </div></SettingsRow></SettingsQueryState>
  );
}

function ProviderCard({ configured, label, makerspaceId, provider }: ProviderCardProps) {
  const queryClient = useQueryClient();
  const [webhookUrl, setWebhookUrl] = useState("");
  const field = `${provider}_webhook_url`;
  const path = `/admin/makerspace/${makerspaceId}/api-settings`;

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: DELIVERY_SETTINGS_KEY(makerspaceId) });

  const saveWebhook = useMutation({
    mutationFn: (value: string) =>
      staffRequest<ApiSettings>(path, {
        method: "PATCH",
        body: JSON.stringify({ [field]: value }),
      }),
    onSuccess: () => {
      setWebhookUrl("");
      invalidate();
    },
  });

  const clearWebhook = useMutation({
    mutationFn: () =>
      staffRequest<ApiSettings>(path, {
        method: "PATCH",
        body: JSON.stringify({ [field]: "" }),
      }),
    onSuccess: () => {
      setWebhookUrl("");
      invalidate();
    },
  });

  const pending = saveWebhook.isPending || clearWebhook.isPending;

  return (
    <section className="rounded-md border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-ink">{label}</h4>
        <Badge label="" tone={configured ? "success" : "neutral"}>
          {configured ? t`Configured` : t`Not configured`}
        </Badge>
      </div>
      <p className="mt-2 text-sm text-muted">
        {t`Paste an incoming webhook URL. The saved URL is never displayed again.`}</p>
      <label className="mt-3 block text-sm font-semibold text-ink">
        {t`${label} incoming webhook URL`}<input
          autoComplete="new-password"
          className="desk-input mt-1 w-full"
          type="password"
          value={webhookUrl}
          onChange={(event) => setWebhookUrl(event.target.value)}
        />
      </label>
      <div className="mt-3">
        <SettingsEditorActions dirty={Boolean(webhookUrl)} onDiscard={() => setWebhookUrl("")} pending={saveWebhook.isPending} disabled={!webhookUrl.trim() || pending} onSave={() => saveWebhook.mutate(webhookUrl.trim())} />

      </div>
      {saveWebhook.error ? (
        <p className="mt-2 text-sm text-danger" role="alert">
          {saveWebhook.error.message}
        </p>
      ) : null}
      {clearWebhook.error ? (
        <p className="mt-2 text-sm text-danger" role="alert">
          {clearWebhook.error.message}
        </p>
      ) : null}
    <SettingsResetAction label={t`Clear ${label} webhook`} consequence="Remove this saved webhook. Alerts will stop reaching this destination until it is configured again." pending={clearWebhook.isPending} disabled={!configured || pending} onConfirm={() => clearWebhook.mutateAsync()} /></section>
  );
}
