import { t } from "@lingui/core/macro";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./StaffPanels";

type Props = { makerspace: Makerspace; settings?: Makerspace; loading: boolean };

export function MakerspaceGeofenceSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const current = settings ?? makerspace;
  const [enabled, setEnabled] = useState(current.geofence_enabled ?? false);
  const [latitude, setLatitude] = useState(String(current.geofence_latitude ?? ""));
  const [longitude, setLongitude] = useState(String(current.geofence_longitude ?? ""));
  const [radius, setRadius] = useState(String(current.geofence_radius_m ?? 25));

  useEffect(() => {
    setEnabled(current.geofence_enabled ?? false);
    setLatitude(String(current.geofence_latitude ?? ""));
    setLongitude(String(current.geofence_longitude ?? ""));
    setRadius(String(current.geofence_radius_m ?? 25));
  }, [current.geofence_enabled, current.geofence_latitude, current.geofence_longitude, current.geofence_radius_m, makerspace.id]);

  const save = useMutation({
    mutationFn: () => staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, { method: "PATCH", body: JSON.stringify({
      geofence_enabled: enabled,
      geofence_latitude: latitude.trim() || null,
      geofence_longitude: longitude.trim() || null,
      geofence_radius_m: Number(radius),
    }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["tenant-bootstrap"] });
    },
  });
  const changed = enabled !== (current.geofence_enabled ?? false) || latitude !== String(current.geofence_latitude ?? "") || longitude !== String(current.geofence_longitude ?? "") || radius !== String(current.geofence_radius_m ?? 25);

  return <SettingsRow label={t`Presence geofence`} helper="Self check-in requires a location inside the configured radius. Without a configured geofence, self check-in is unavailable. GPS can be spoofed. Staff or kiosk check-in is the alternative. Browsers require HTTPS or localhost for location access."><div className="@container grid min-w-0 gap-4"><form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); if (changed) save.mutate(); }}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><Badge label="" tone={enabled ? "success" : "neutral"}>{enabled ? t`On` : t`Off`}</Badge></div></div><label className="min-h-11 flex items-center gap-2 text-sm font-semibold text-ink"><input type="checkbox" checked={enabled} disabled={loading || save.isPending} onChange={(event) => setEnabled(event.target.checked)} /> {t` Enable geofence`}</label></div>
    <div className="grid gap-3 @lg:grid-cols-3"><label className="grid gap-1 text-sm font-semibold text-ink">{t`Latitude`}<input className="desk-input" inputMode="decimal" value={latitude} onChange={(event) => setLatitude(event.target.value)} placeholder="12.971599" /></label><label className="grid gap-1 text-sm font-semibold text-ink">{t`Longitude`}<input className="desk-input" inputMode="decimal" value={longitude} onChange={(event) => setLongitude(event.target.value)} placeholder="77.594566" /></label><label className="grid gap-1 text-sm font-semibold text-ink">{t`Radius (metres)`}<input className="desk-input" type="number" min="1" value={radius} onChange={(event) => setRadius(event.target.value)} /></label></div>
    {save.error ? <p className="text-sm text-danger" role="alert">{save.error.message}</p> : null}<SettingsEditorActions dirty={changed} onDiscard={() => { setEnabled(current.geofence_enabled ?? false); setLatitude(String(current.geofence_latitude ?? "")); setLongitude(String(current.geofence_longitude ?? "")); setRadius(String(current.geofence_radius_m ?? 25)); }} pending={save.isPending} disabled={loading || save.isPending || !changed} />
  </form></div></SettingsRow>;
}
