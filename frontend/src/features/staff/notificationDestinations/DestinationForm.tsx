import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import {
  type NotificationDestination,
  type DestinationScope,
  EMPTY_SCOPE,
} from "../notificationDestinationTypes";
import { DESTINATIONS_KEY } from "./channels";
import { ScopePicker } from "./ScopePicker";
import { SigningSecretReveal } from "./SigningSecretReveal";
import { type ScopeOptions } from "./scopeOptions";

export function DestinationForm({
  basePath,
  channels,
  destination,
  makerspaceId,
  onDone,
  options,
}: {
  basePath: string;
  channels: readonly { key: string; label: string }[];
  destination?: NotificationDestination;
  makerspaceId: number;
  onDone: () => void;
  options: ScopeOptions;
}) {
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState(destination?.channel ?? channels[0]?.key ?? "slack");
  const [label, setLabel] = useState(destination?.label ?? "");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [chatId, setChatId] = useState(destination?.telegram_chat_id ?? "");
  const [signingSecret, setSigningSecret] = useState("");
  const [isActive, setIsActive] = useState(destination?.is_active ?? true);
  const [payloadVersion, setPayloadVersion] = useState(destination?.payload_version ?? 1);
  const [scope, setScope] = useState<DestinationScope>(destination?.scope ?? EMPTY_SCOPE);
  const [error, setError] = useState("");
  // Parity A10: on create the server generates the webhook secret and returns it this once.
  const [generatedSecret, setGeneratedSecret] = useState("");

  const save = useMutation({
    mutationFn: () =>
      staffRequest<NotificationDestination & { signing_secret?: string }>(
        destination ? `${basePath}/${destination.id}` : basePath,
        {
          method: destination ? "PUT" : "POST",
          body: JSON.stringify({
            channel,
            label,
            // Blank on edit means "keep the stored credential" — it cannot be read back,
            // so requiring it to rename a room would force a re-entry.
            ...(webhookUrl ? { webhook_url: webhookUrl } : {}),
            ...(channel === "webhook" && signingSecret ? { signing_secret: signingSecret } : {}),
            telegram_chat_id: channel === "telegram" ? chatId : "",
            is_active: isActive,
            payload_version: payloadVersion,
            scope,
          }),
        },
      ),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: DESTINATIONS_KEY(makerspaceId) });
      if (saved?.signing_secret) setGeneratedSecret(saved.signing_secret);
      else onDone();
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : t`Could not save this room.`),
  });

  if (generatedSecret) return <SigningSecretReveal secret={generatedSecret} onDone={onDone} />;

  return (
    <form
      className="@container grid gap-3 rounded-md border border-line bg-bg p-3"
      onSubmit={(event) => {
        event.preventDefault();
        setError("");
        save.mutate();
      }}
    >
      <div className="grid gap-2 @md:grid-cols-2">
        <label className="grid gap-1 text-sm">
          <span className="text-muted">{t`Channel`}</span>
          <select
            className="desk-input max-w-full"
            disabled={Boolean(destination)}
            onChange={(event) => setChannel(event.target.value as typeof channel)}
            value={channel}
          >
            {channels.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-muted">{t`Room name`}</span>
          <input
            className="desk-input"
            onChange={(event) => setLabel(event.target.value)}
            placeholder={t`Laser team`}
            required
            value={label}
          />
        </label>
      </div>

      {channel === "telegram" ? (
        <label className="grid gap-1 text-sm">
          <span className="text-muted">{t`Telegram chat ID`}</span>
          <input
            className="desk-input"
            onChange={(event) => setChatId(event.target.value)}
            placeholder="-1001234567890"
            required
            value={chatId}
          />
          <span className="text-xs text-muted">
            {t`Add this makerspace's bot to each group. Alerts are outbound only; review requests in the staff console.`}</span>
        </label>
      ) : (
        <label className="grid gap-1 text-sm">
          <span className="text-muted">
            {t`Incoming webhook URL`}{destination?.credential_set ? t` (leave blank to keep)` : ""}
          </span>
          <input
            autoComplete="off"
            className="desk-input"
            onChange={(event) => setWebhookUrl(event.target.value)}
            placeholder="https://hooks.example.com/…"
            type="password"
            value={webhookUrl}
          />
        </label>
      )}

      {channel === "webhook" ? (
        <label className="grid gap-1 text-sm">
          <span className="text-muted">
            {t`Signing secret`}{destination?.signing_secret_set ? t` (leave blank to keep)` : t` (optional)`}
          </span>
          <input
            autoComplete="off"
            className="desk-input"
            minLength={16}
            onChange={(event) => setSigningSecret(event.target.value)}
            placeholder={destination ? t`At least 16 characters` : t`Leave blank to generate one`}
            type="password"
            value={signingSecret}
          />
          <span className="text-xs text-muted">
            {destination ? t`To replace the secret safely, use Rotate signing secret in the room's menu instead.`
              : t`Leave it blank and a strong secret is generated and shown to you once after saving.`}{" "}
            {t`Every notification routed to this endpoint arrives as JSON with an HMAC-SHA256 signature over the exact body, in the X-SpaceWorks-Signature header.`}</span>
        </label>
      ) : null}

      {channel === "webhook" ? <label className="grid gap-1 text-sm">{t`Payload format`}<select className="desk-input max-w-full" value={payloadVersion} onChange={(event) => setPayloadVersion(Number(event.target.value) as 1 | 2)}>
            <option value={1}>{t`v1 legacy envelope`}</option><option value={2}>{t`v2 structured domain IDs`}</option>
          </select>
      </label> : null}
      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input
          checked={isActive}
          onChange={(event) => setIsActive(event.target.checked)}
          type="checkbox"
        />
        <span>{t`Deliver to this room`}</span>
      </label>

      <ScopePicker onChange={setScope} options={options} scope={scope} />

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button className="desk-button-primary" disabled={save.isPending} type="submit">
          {save.isPending ? t`Saving…` : t`Save room`}
        </button>
        <button className="desk-button-ghost" onClick={onDone} type="button">
          {t`Cancel`}</button>
      </div>
    </form>
  );
}
