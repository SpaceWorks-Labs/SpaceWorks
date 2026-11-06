import { t } from "@lingui/core/macro";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./StaffPanels";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

export function MakerspaceLocationSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const currentLocation = settings?.location ?? makerspace.location ?? "";
  const currentMapUrl = settings?.map_url ?? makerspace.map_url ?? "";
  const [locationInput, setLocationInput] = useState(currentLocation);
  const [mapUrlInput, setMapUrlInput] = useState(currentMapUrl);

  useEffect(() => {
    setLocationInput(currentLocation);
    setMapUrlInput(currentMapUrl);
  }, [currentLocation, currentMapUrl, makerspace.id]);

  const updateLocation = useMutation({
    mutationFn: () =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          location: locationInput.trim(),
          map_url: mapUrlInput.trim(),
        }),
      }),
    onSuccess: (updated) => {
      setLocationInput(updated.location ?? "");
      setMapUrlInput(updated.map_url ?? "");
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["public-makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["tenant-bootstrap"] });
    },
  });

  const changed =
    locationInput.trim() !== currentLocation ||
    mapUrlInput.trim() !== currentMapUrl;
  const saveDisabled = loading || updateLocation.isPending || !changed;
  const savedMapUrl = currentMapUrl.trim();

  return (
    <SettingsRow label={t`Location`} helper={t`Public location label and optional Google Maps link shown on public pages.`}><div className="@container grid min-w-0 gap-4">
      <form
        className="grid min-w-0 gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!saveDisabled) {
            updateLocation.mutate();
          }
        }}
      >
        <div className="grid min-w-0 gap-3 @md:grid-cols-[minmax(0,1fr)_auto] @md:items-start">
          <div className="grid min-w-0 max-w-2xl gap-2">
            <div className="flex flex-wrap items-center gap-2">

              <Badge label="" tone={savedMapUrl ? "success" : "neutral"}>
                {savedMapUrl ? t`Maps link set` : t`Text only`}
              </Badge>
            </div>

          </div>
          <SettingsEditorActions dirty={changed} onDiscard={() => { setLocationInput(currentLocation); setMapUrlInput(currentMapUrl); }} pending={updateLocation.isPending} disabled={saveDisabled} />
        </div>

        <div className="grid min-w-0 gap-3 @xl:grid-cols-2">
          <label className="grid min-w-0 gap-2 text-sm font-semibold text-ink">
            <span>{t`Location label`}</span>
            <input
              className="desk-input"
              value={locationInput}
              onChange={(event) => setLocationInput(event.target.value)}
              placeholder={t`Main lab, downtown campus`}
            />
          </label>
          <label className="grid min-w-0 gap-2 text-sm font-semibold text-ink">
            <span>{t`Google Maps link`}</span>
            <input
              className="desk-input"
              value={mapUrlInput}
              onChange={(event) => setMapUrlInput(event.target.value)}
              placeholder="https://maps.app.goo.gl/..."
            />
            <span className="text-xs font-normal text-muted">{t`Open Google Maps → Share → Copy link → paste here`}</span>
          </label>
        </div>

        {savedMapUrl ? (
          <a
            className="w-fit text-xs font-semibold uppercase text-accent-ink hover:underline"
            href={savedMapUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t`Open in Maps ↗`}</a>
        ) : null}
        {updateLocation.error ? (
          <p className="text-sm text-danger">{updateLocation.error.message}</p>
        ) : null}
      </form>
    </div></SettingsRow>
  );
}
