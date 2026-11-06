import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, StatusPill, type Tone } from "../../components/ui";
import { CHANNEL_SPECS, type ChannelSpec } from "./channelCatalog";
import { useChannels, type Channel } from "./channelsApi";
import { ChannelSetupForm } from "./ChannelSetupForm";
import { ChannelTestSend } from "./ChannelTestSend";

function summary(spec: ChannelSpec, row?: Channel): { label: string; tone: Tone } {
  // No settings row means today's behaviour: email sends and existing rooms post.
  if (!row) return { label: spec.key === "email" ? t`On (default)` : t`Not set up`, tone: "neutral" };
  if (!row.enabled) return { label: t`Off`, tone: "neutral" };
  if (row.activation_hold) return { label: t`Review needed`, tone: "warn" };
  const parts = [row.room_enabled && spec.rooms ? "rooms" : "", row.personal_enabled ? "personal" : ""].filter(Boolean);
  return { label: parts.length ? t`On · ${parts.join(" + ")}` : t`On`, tone: "success" };
}

/**
 * Space Manager channel setup: which mediums this space uses, how (staff rooms vs
 * personal messages), their credentials and a test send. Only what is enabled here is
 * offered to staff and members when they choose where their notifications go.
 */
export function ChannelSetupPanel({ makerspaceId, enabledModules }: { makerspaceId: number; enabledModules: readonly string[] }) {
  const channels = useChannels(makerspaceId);
  const [open, setOpen] = useState<string | null>(null);
  if (channels.isLoading) return <p className="py-4 text-sm text-muted">{t`Loading channels…`}</p>;
  if (channels.error) return <ErrorBlock error={new Error(t`Couldn't load channel settings (${channels.error.message}).`)}
    onRetry={() => { void channels.refetch(); }} />;
  const rows = new Map((channels.data?.results ?? []).map(row => [row.channel, row]));
  return <ul className="grid min-w-0 gap-3 py-4" aria-label={t`Notification channels`}>
    {CHANNEL_SPECS.map(spec => {
      const row = rows.get(spec.key);
      const state = summary(spec, row);
      const expanded = open === spec.key;
      const panelId = `channel-setup-${spec.key}`;
      return <li key={spec.key} className="min-w-0 rounded-xl border border-line bg-panel">
        <button type="button" aria-expanded={expanded} aria-controls={panelId} onClick={() => setOpen(expanded ? null : spec.key)}
          className="flex min-h-11 w-full flex-wrap items-center gap-3 rounded-xl px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
          <span className="grid min-w-0 flex-1 gap-0.5"><span className="font-semibold text-ink">{spec.label}</span>
            <span className="text-sm text-muted">{spec.description}</span></span>
          <StatusPill label={state.label} tone={state.tone} />
        </button>
        {expanded ? <div id={panelId} className="grid min-w-0 gap-4 border-t border-line p-4">
          <ChannelSetupForm key={`${spec.key}:${row?.generation ?? 0}`} makerspaceId={makerspaceId} spec={spec} row={row}
            moduleInstalled={!spec.module || enabledModules.includes(spec.module)} />
          {row ? <ChannelTestSend makerspaceId={makerspaceId} channel={row} /> : null}
        </div> : null}
      </li>;
    })}
  </ul>;
}
