import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import { SettingsRow } from "../../components/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./StaffPanels";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

export function MakerspacePublicStatsSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const publicStatsEnabled = settings?.public_stats_enabled ?? makerspace.public_stats_enabled ?? false;
  const showHolderNames =
    settings?.public_stats_show_holder_names ?? makerspace.public_stats_show_holder_names ?? false;

  const invalidateSettings = () => {
    queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
    queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
  };
  const updatePublicStats = useMutation({
    mutationFn: (next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_stats_enabled: next }),
      }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updatePublicStats`),
    onSuccess: async (_data, next) => {
      await (invalidateSettings)();
      toast(`Public stats turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updatePublicStats`, undo: async () => {
        await ((next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_stats_enabled: next }),
      }))(!next);
        await (invalidateSettings)();
      } });
    },
  });
  const updateHolderNames = useMutation({
    mutationFn: (next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_stats_show_holder_names: next }),
      }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updateHolderNames`),
    onSuccess: async (_data, next) => {
      await (invalidateSettings)();
      toast(`Public borrower names turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updateHolderNames`, undo: async () => {
        await ((next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_stats_show_holder_names: next }),
      }))(!next);
        await (invalidateSettings)();
      } });
    },
  });

  return <>
    <SettingsRow label="Public stats page" helper="Publish activity, popular hardware and current loans. Borrower names have their own privacy setting below.">
      <div className="@container grid gap-3"><Badge label="" tone={publicStatsEnabled ? "success" : "neutral"}>{publicStatsEnabled ? "On" : "Off"}</Badge>
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={publicStatsEnabled}
          disabled={loading || updatePublicStats.isPending} onChange={event => updatePublicStats.mutate(event.target.checked)} />Publish public stats</label>
        <p className="text-sm text-muted">The stats page at /m/{makerspace.slug}/stats returns 404 when disabled.</p>
        {updatePublicStats.error ? <p role="alert" className="text-sm text-danger">{updatePublicStats.error.message}</p> : null}
      </div>
    </SettingsRow>
    <SettingsRow label="Public borrower names" helper="When on, current loans publish the borrower’s name on the public stats page. When off, every borrower is shown as Member.">
      <div className="@container grid gap-3"><Badge label="" tone={showHolderNames ? "warn" : "neutral"}>{showHolderNames ? "On" : "Off"}</Badge>
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={showHolderNames}
          disabled={loading || updateHolderNames.isPending} onChange={event => updateHolderNames.mutate(event.target.checked)} />Publish borrower names publicly</label>
        {updateHolderNames.error ? <p role="alert" className="text-sm text-danger">{updateHolderNames.error.message}</p> : null}
      </div>
    </SettingsRow>
  </>;
}
