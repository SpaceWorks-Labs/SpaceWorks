import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, StatusPill } from "../../components/ui";
import { CHANNEL_LABELS } from "./channelCatalog";
import { useEndpoints, useRevokeEndpoint, type ChannelKey, type Endpoint } from "./channelsApi";
import { ConnectChannel } from "./ConnectChannel";

/** The person's own connections, one row per channel the space enabled for personal delivery. */
export function PersonalChannels({ makerspaceId, channels, member = false }: {
  makerspaceId: number; channels: readonly ChannelKey[]; member?: boolean;
}) {
  const endpoints = useEndpoints(makerspaceId, member);
  const revoke = useRevokeEndpoint(makerspaceId, member);
  const [connecting, setConnecting] = useState<ChannelKey | null>(null);
  if (endpoints.isLoading) return <p className="text-sm text-muted">{t`Loading your channels…`}</p>;
  if (endpoints.error) return <ErrorBlock error={endpoints.error} onRetry={() => { void endpoints.refetch(); }} />;
  if (!channels.length) return <p className="text-sm text-muted">{t`This space has not turned on any chat channels for personal messages yet.`}</p>;
  const live = new Map<ChannelKey, Endpoint>();
  for (const row of endpoints.data?.results ?? []) if (!row.revoked_at && row.verification_state === "verified" && !live.has(row.channel)) live.set(row.channel, row);
  return <ul className="grid min-w-0 gap-3" aria-label={t`Your connected channels`}>
    {channels.map(channel => {
      const endpoint = live.get(channel);
      const label = CHANNEL_LABELS[channel] ?? channel;
      return <li key={channel} className="grid min-w-0 gap-3 rounded-lg border border-line p-3">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <span className="min-w-0 flex-1 font-semibold text-ink">{label}</span>
          <StatusPill label={endpoint?.effective_valid ? t`Connected` : endpoint ? t`Reconnect required` : t`Not connected`} tone={endpoint?.effective_valid ? "success" : "neutral"} />
          {endpoint ? <button type="button" className="desk-button" disabled={revoke.isPending}
            onClick={() => revoke.mutate(endpoint.id)}>{t`Disconnect`}</button> : null}
          {!endpoint?.effective_valid && connecting !== channel ? <button type="button" className="desk-button" onClick={() => setConnecting(channel)}>{t`Connect`}</button> : null}
        </div>
        {endpoint?.verified_at ? <p className="text-xs text-muted">{t`Connected ${new Date(endpoint.verified_at).toLocaleDateString(formatLocale())}.`}</p> : null}
        {connecting === channel && !endpoint?.effective_valid ? <ConnectChannel makerspaceId={makerspaceId} channel={channel} member={member}
          onDone={() => setConnecting(null)} /> : null}
      </li>;
    })}
    {revoke.error ? <li role="alert" className="text-sm text-danger">{revoke.error.message}</li> : null}
  </ul>;
}

export function connectedChannels(endpoints: readonly Endpoint[] | undefined): Set<ChannelKey> {
  return new Set((endpoints ?? []).filter(row => row.effective_valid).map(row => row.channel));
}
