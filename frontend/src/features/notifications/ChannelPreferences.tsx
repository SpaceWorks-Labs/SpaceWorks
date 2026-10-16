import { useState } from "react";

import { CATEGORY_LABELS, CHANNEL_LABELS, CONNECTABLE } from "./channelCatalog";
import { useSavePreferences, type ChannelKey, type Selection } from "./channelsApi";

/**
 * Per category, which channels this person receives on (several may be chosen) and whether
 * email may stand in when none of them could deliver. Only channels the space enabled are
 * listed; chat channels can be chosen once connected. Safety and account mail stays email.
 */
export function ChannelPreferences({ makerspaceId, preferences, connected, member = false }: {
  makerspaceId: number; preferences: Selection[]; connected: ReadonlySet<ChannelKey>; member?: boolean;
}) {
  const [draft, setDraft] = useState(preferences);
  const save = useSavePreferences(makerspaceId, member);
  const shown = draft.filter(row => row.available_channels?.length);
  const dirty = JSON.stringify(draft) !== JSON.stringify(preferences);
  const update = (category: string, patch: Partial<Selection>) =>
    setDraft(current => current.map(row => row.category === category ? { ...row, ...patch } : row));
  if (!shown.length) return <p className="text-sm text-muted">There are no notifications to choose channels for in this space yet.</p>;
  return <form className="grid min-w-0 gap-3" aria-label="Where your notifications go" onSubmit={event => {
    event.preventDefault();
    // The PUT replaces every category, so the whole list (defaults included) is sent.
    save.mutate(draft, { onSuccess: data => setDraft(data.preferences) });
  }}>
    {shown.map(row => {
      const name = CATEGORY_LABELS[row.category] ?? row.category.replace(/_/g, " ");
      return <fieldset key={row.category} className="grid min-w-0 gap-1 rounded-lg border border-line p-3">
        <legend className="px-1 text-sm font-semibold text-ink">{name}</legend>
        <div className="flex min-w-0 flex-wrap gap-x-4">
          {(row.available_channels ?? []).map(channel => {
            const needsConnection = CONNECTABLE.includes(channel) && !connected.has(channel);
            const checked = row.channels.includes(channel);
            return <label key={channel} className="flex min-h-11 items-center gap-2 text-sm">
              <input className="h-4 w-4" type="checkbox" checked={checked} disabled={save.isPending || (needsConnection && !checked)}
                aria-label={`${name}: ${CHANNEL_LABELS[channel] ?? channel}`}
                onChange={event => update(row.category, { channels: event.target.checked
                  ? [...row.channels, channel] : row.channels.filter(item => item !== channel) })} />
              <span>{CHANNEL_LABELS[channel] ?? channel}{needsConnection ? <span className="text-muted"> (connect first)</span> : null}</span>
            </label>;
          })}
        </div>
        <label className="flex min-h-11 items-center gap-2 text-sm text-muted">
          <input className="h-4 w-4" type="checkbox" checked={row.email_fallback} disabled={save.isPending}
            onChange={event => update(row.category, { email_fallback: event.target.checked })} />
          Email me if none of these could deliver
        </label>
      </fieldset>;
    })}
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    {save.isSuccess && !dirty ? <p role="status" className="text-sm text-muted">Saved.</p> : null}
    <div className="flex flex-wrap gap-2">
      <button className="desk-button" type="submit" disabled={!dirty || save.isPending}>{save.isPending ? "Saving…" : "Save choices"}</button>
      {dirty ? <button className="desk-button" type="button" onClick={() => setDraft(preferences)}>Discard</button> : null}
    </div>
  </form>;
}
