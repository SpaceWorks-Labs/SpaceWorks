import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { StructuredApiError, staffRequest } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { localDateTime } from "../events/stagedForms/formPayload";

/** Decision 221(i): an invitation limited to tracks and/or a time window. Empty = the inviter's own limit. */
export type InviteLimit = { track_ids: number[]; valid_from: string; valid_until: string };
export const emptyInviteLimit: InviteLimit = { track_ids: [], valid_from: "", valid_until: "" };
type Track = { id: number; name: string };
type TrackPage = { results: Track[] };

export function useEventTracks(eventId: number, enabled = true) {
  return useQuery({ queryKey: ["event-staff-access", "event", eventId, "tracks"], retry: false, enabled,
    queryFn: () => staffRequest<TrackPage>(`/admin/events/${eventId}/tracks/?page=1`),
    select: (data) => ({ results: (data?.results ?? []).filter((row) => typeof row?.id === "number" && typeof row?.name === "string") }) });
}

/** Decision 221(i): a limited co-organizer's form starts from their own limit (`event.my_limit`), so the
 *  invitation they send is the same track/window unless they narrow it. Null (unlimited) starts empty. */
export function inviteLimitFromMine(mine: { track_ids: number[]; valid_from: string | null; valid_until: string | null } | null | undefined): InviteLimit {
  if (!mine) return emptyInviteLimit;
  return { track_ids: [...mine.track_ids], valid_from: localDateTime(mine.valid_from), valid_until: localDateTime(mine.valid_until) };
}

const iso = (value: string) => (value ? new Date(value).toISOString() : null);

/** Only the parts that were set are sent, so the server's inheritance of the inviter's own limit applies to the rest. */
export function inviteLimitInput(limit: InviteLimit) {
  return {
    ...(limit.track_ids.length ? { track_ids: limit.track_ids } : {}),
    ...(limit.valid_from ? { valid_from: iso(limit.valid_from) } : {}),
    ...(limit.valid_until ? { valid_until: iso(limit.valid_until) } : {}),
  };
}

export function validateInviteLimit(limit: InviteLimit): string | null {
  if (limit.valid_from && limit.valid_until && new Date(limit.valid_until) <= new Date(limit.valid_from)) return t`The end must be after the start.`;
  return null;
}

/** The 403 a co-organizer gets for asking wider than their own grant. */
export function inviteLimitError(error: unknown): string | null {
  if (!(error instanceof StructuredApiError) || error.status !== 403) return null;
  return t`This invitation would reach beyond your own track or time limit. Choose tracks and dates inside your own access, or leave them empty to use your own limit.`;
}

/** "Tracks: A, B · From … · Until …", or "" for an unlimited row. */
export function inviteLimitText(row: { track_ids?: number[]; valid_from?: string | null; valid_until?: string | null }, tracks: Track[] = []) {
  const parts: string[] = [];
  if (row.track_ids?.length) {
    const names = row.track_ids.map((id) => tracks.find((track) => track.id === id)?.name ?? `#${id}`).join(", ");
    parts.push(t`Tracks: ${names}`);
  }
  if (row.valid_from) parts.push(t`From ${formatDateTime(row.valid_from)}`);
  if (row.valid_until) parts.push(t`Until ${formatDateTime(row.valid_until)}`);
  return parts.join(" · ");
}

export function EventInviteLimitFields({ value, onChange, tracks, disabled, hint }: {
  value: InviteLimit; onChange: (value: InviteLimit) => void; tracks: Track[]; disabled: boolean; hint?: string;
}) {
  return <fieldset disabled={disabled} className="grid min-w-0 gap-3">
    <legend className="mb-1 text-sm font-semibold text-ink">{t`Limit (optional)`}</legend>
    <p className="text-sm text-muted">{hint ?? t`Leave these empty to give the same track and time limit you have yourself. You can narrow it, never widen it.`}</p>
    {tracks.length ? <div className="grid gap-x-4 sm:grid-cols-2" role="group" aria-label={t`Limit to tracks`}>
      <p className="text-sm font-semibold text-ink sm:col-span-2">{t`Limit to tracks`}</p>
      {tracks.map((track) => <label key={track.id} className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="checkbox" checked={value.track_ids.includes(track.id)} onChange={(event) => onChange({ ...value,
          track_ids: event.target.checked ? [...value.track_ids, track.id] : value.track_ids.filter((id) => id !== track.id) })} />
        <span className="[overflow-wrap:anywhere]">{track.name}</span></label>)}
    </div> : null}
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Valid from`}<input className="desk-input w-full min-w-0 font-normal" type="datetime-local"
        value={value.valid_from} onChange={(event) => onChange({ ...value, valid_from: event.target.value })} /></label>
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Valid until`}<input className="desk-input w-full min-w-0 font-normal" type="datetime-local"
        value={value.valid_until} onChange={(event) => onChange({ ...value, valid_until: event.target.value })} /></label>
    </div>
  </fieldset>;
}
