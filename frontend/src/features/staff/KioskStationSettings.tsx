import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsRow } from "../../components/ui";
import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge, ListRow, OverflowMenu, EmptyState } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { type Makerspace, useStaffGet } from "./StaffPanels";

type KioskStation = {
  id: number;
  name: string;
  kind: "scanner" | "handover";
  enabled: boolean;
  public_token: string | null;
  version: number | null;
  station_url: string | null;
  pin?: string;
};

// Phase 9b kiosk Station administration. A freshly created or rotated PIN is shown once
// from the mutation result and never cached; the list query never carries a PIN.
export function KioskStationSettings({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const key = ["kiosk-stations", makerspace.id];
  const stations = useStaffGet<KioskStation[]>(key, `/admin/makerspace/${makerspace.id}/kiosk-stations/`);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<KioskStation["kind"]>("handover");
  const [secret, setSecret] = useState<KioskStation | null>(null);
  const [revealFor, setRevealFor] = useState<KioskStation | null>(null);
  const [password, setPassword] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: key });

  const create = useMutation({
    mutationFn: () => staffRequest<KioskStation>(`/admin/makerspace/${makerspace.id}/kiosk-stations/`, {
      method: "POST", body: JSON.stringify({ name, kind }),
    }),
    onSuccess: (station) => { setSecret(station); setName(""); refresh(); },
  });
  const rotate = useMutation({
    mutationFn: (id: number) => staffRequest<KioskStation>(`/admin/kiosk-stations/${id}/rotate/`, { method: "POST" }),
    onSuccess: (station) => { setSecret(station); refresh(); },
  });
  const disable = useMutation({
    mutationFn: (id: number) => staffRequest<KioskStation>(`/admin/kiosk-stations/${id}/`, { method: "DELETE" }),
    onSuccess: () => { setSecret(null); refresh(); },
  });

  const reveal = useMutation({
    mutationFn: (station: KioskStation) => staffRequest<{ pin: string; version: number }>(`/admin/kiosk-stations/${station.id}/reveal/`, {
      method: "POST", body: JSON.stringify({ current_password: password }),
    }),
    onSuccess: (data, station) => { setSecret({ ...station, pin: data.pin }); setRevealFor(null); setPassword(""); },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  return <SettingsRow label="Kiosk stations" helper="A Station PIN only unlocks the kiosk. Every handover still needs a signed-in staff operator, and is recorded against that person."><div className="grid min-w-0 gap-4">
    <div className="grid max-w-2xl gap-2">


    </div>
    <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={submit}>
      <label className="grid gap-1 text-sm">Name<input id="kiosk-station-name" className="desk-input" required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label className="grid gap-1 text-sm">Kind<select className="desk-input" value={kind} onChange={(event) => setKind(event.target.value as KioskStation["kind"])}>
        <option value="handover">Handover</option>
        <option value="scanner">Scanner</option>
      </select></label>
      <button className="desk-button-primary" type="submit" disabled={create.isPending || !name.trim()}>Create station</button>
    </form>
    {create.isError ? <p className="mt-2 text-sm text-danger" role="alert">The station could not be created.</p> : null}
    {secret?.pin ? <div className="mt-4 rounded-md border border-line p-3" role="status">
      <p className="text-sm">PIN for <strong>{secret.name}</strong> (shown once): <span className="tabular-nums text-lg tracking-widest">{secret.pin}</span></p>
      {secret.station_url ? <p className="mt-1 break-all code-text text-xs text-muted">{secret.station_url}</p> : null}
    </div> : null}

    {!stations.isLoading && !stations.error && !stations.data?.length ? <EmptyState message="No stations yet. Create your first station." /> : null}
    {rotate.error || disable.error ? <p role="alert" className="text-sm text-danger">{(rotate.error ?? disable.error)?.message}</p> : null}
    <SettingsQueryState query={stations} resource="kiosk stations" />
    <ul className="mt-4 grid gap-2">
      {(stations.data ?? []).map(station => <li key={station.id}>
        <ListRow title={station.name} meta={<span className="flex flex-wrap items-center gap-2">
          <Badge label={station.kind} /><Badge label={station.enabled ? "Enabled" : "Disabled"} tone={station.enabled ? "success" : "warn"} />
        </span>} right={<div className="flex items-center gap-2">
          <button className="desk-button" type="button" disabled={rotate.isPending} onClick={() => rotate.mutate(station.id)}>{station.enabled ? "Rotate PIN" : "Re-enable with new PIN"}</button>
          {station.enabled ? <OverflowMenu label={`Actions for ${station.name}`} actions={[
            { label: "Reveal PIN", onClick: () => { setRevealFor(station); setPassword(""); } },
            { label: "Disable", tone: "danger", onClick: () => disable.mutate(station.id), pending: disable.isPending },
          ]} /> : null}
        </div>} />
      </li>)}
    </ul>
    {revealFor ? <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); reveal.mutate(revealFor); }}>
      <label className="grid gap-1 text-sm">Your current password to reveal {revealFor.name}<input className="desk-input" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <button className="desk-button-primary" type="submit" disabled={reveal.isPending || !password}>Reveal</button>
      <button className="desk-button" type="button" onClick={() => setRevealFor(null)}>Cancel</button>
      {reveal.isError ? <p className="text-sm text-danger" role="alert">The PIN could not be revealed. Check your password, or rotate the PIN instead.</p> : null}
    </form> : null}
  </div></SettingsRow>;
}
