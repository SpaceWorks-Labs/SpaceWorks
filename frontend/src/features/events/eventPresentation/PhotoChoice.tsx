import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";

import type { ProfileOption as Option, Presentation } from '../../../generated/api';
import { CommandSession } from '../hackathonAdmission/transport';
import { sessionScope, useClearDeniedQuery } from '../../staff/eventProgramme/sessionScope';

export function PhotoChoice({ makerspaceId, eventId, eventName, actorId = 0 }: { makerspaceId: number; eventId: number; eventName: string; actorId?: number }) {
  const base = `/member/makerspaces/${makerspaceId}/events/${eventId}`;
  const key = ["event-presentation", actorId, makerspaceId, eventId, ...sessionScope()];
  const commands = useRef(new CommandSession());
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const options = useQuery({ queryKey: [...key, "choices"], queryFn: () => memberRequest<{ options: Option[] }>(`${base}/profile-photo-options/`), staleTime: 0, gcTime: 0 });
  const current = useQuery({ queryKey: key, queryFn: () => memberRequest<Presentation>(`${base}/presentation/`), staleTime: 0, gcTime: 0 });
  const [profileId, setProfileId] = useState<number | null>(null);
  const [printConsent, setPrintConsent] = useState(false);
  const [scopes, setScopes] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { if (current.data && !dirty) {
    setProfileId(current.data.profile_id ?? null);
    setPrintConsent(current.data.print_photo_consent); setScopes(current.data.public_card_scopes);
  } }, [current.data, dirty]);
  const chosen = options.data?.options.find((row) => row.profile_id === profileId);
  const save = useMutation({ mutationFn: () => commands.current.send<Presentation>(`/api/v1${base}/presentation/`, "PATCH", { expected_version: current.data?.version ?? 0,
    profile_id: chosen?.profile_id ?? null, membership_id: chosen?.membership_id ?? null,
    source_revision: chosen?.source_revision ?? null, print_photo_consent: Boolean(chosen && printConsent),
    public_card_consent: Boolean(chosen && scopes.length), public_card_scopes: chosen ? scopes : [],
  }), onSuccess: async () => { setDirty(false); await Promise.all([client.invalidateQueries({ queryKey: key }), client.invalidateQueries({ queryKey: [...key, "choices"] })]); } });
  const error = current.error || options.error || save.error;
  const denied = useClearDeniedQuery(error, key);
  if (denied) return <p role="alert">Photo choices are no longer available for your access.</p>;
  return <details className="rounded-control border border-line p-3" onToggle={event => setOpen(event.currentTarget.open)}><summary className="min-h-11 cursor-pointer font-semibold text-ink">Badge photo and public cards</summary>
    {open ? <><p className="my-2 text-sm text-muted">Choose a profile for {eventName}. No profile is selected automatically. Photos come from your existing makerspace profiles.</p>
    {current.isLoading || options.isLoading ? <p role="status">Loading your choices…</p> : <fieldset disabled={save.isPending || !current.data} className="grid gap-3">
      <label className="grid gap-1 text-sm">Profile source<select className="desk-input" value={profileId ?? ""} onChange={(event) => {
        setDirty(true); setProfileId(event.target.value ? Number(event.target.value) : null); setPrintConsent(false); setScopes([]);
      }}><option value="">No photo or profile</option>{options.data?.options.map((row) => <option value={row.profile_id} key={row.profile_id}>{row.makerspace_name} — {row.has_photo ? "photo available" : "no photo"}</option>)}</select></label>
      {chosen ? <p className="text-sm text-muted">Source: {chosen.makerspace_name}. Destination: {eventName}. This choice grants no makerspace access.</p> : <p className="text-sm text-muted">Your badge uses initials. No photo is fetched.</p>}
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" disabled={!chosen} checked={printConsent} onChange={(event) => { setDirty(true); setPrintConsent(event.target.checked); }} />Use this selected photo on this event’s printed badge</label>
      <fieldset disabled={!chosen?.public_eligible} className="grid gap-1"><legend className="text-sm font-semibold text-ink">Public card consent (separate from printing)</legend>
        {["team", "mentor", "judge"].map((scope) => <label className="flex min-h-11 items-center gap-2 text-sm" key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={(event) => {
          setDirty(true); setScopes(event.target.checked ? [...scopes, scope] : scopes.filter((value) => value !== scope));
        }} />Show my chosen public profile on this event’s {scope} cards</label>)}
      </fieldset>
      <p className="text-xs text-muted">Public cards also require your profile to stay public and the organizer to publish that surface. Revoking consent blocks new reads and printing; downloaded images and paper cannot be recalled.</p>
      <button type="button" className="desk-button" disabled={!dirty} onClick={() => save.mutate()}>Save photo choices</button>
      {save.isSuccess ? <p role="status" className="text-sm text-success-ink">Photo choices saved.</p> : null}
    </fieldset>}
    {error ? <p className="text-sm text-danger" role="alert">{error.message}</p> : null}
    </> : null}
  </details>;
}
