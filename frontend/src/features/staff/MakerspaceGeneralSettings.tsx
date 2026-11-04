import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import { SettingsRow } from "../../components/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { MakerspacePublicSiteSettings } from "./MakerspacePublicSiteSettings";
import type { Makerspace } from "./panels/shared";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

/**
 * Default loan days and the rest of the loan policy moved to the Lending section (and the
 * Inventory Manager's Lending settings): they are one policy, edited through one endpoint.
 */
export function MakerspaceGeneralSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const publicInventoryEnabled =
    settings?.public_inventory_enabled ?? makerspace.public_inventory_enabled ?? true;

  const refreshSettings = () => {
    queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
    queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
  };

  const updatePublicInventory = useMutation({
    mutationFn: (next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_inventory_enabled: next }),
      }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updatePublicInventory`),
    onSuccess: async (_data, next) => {
      await (refreshSettings)();
      toast(`Public inventory turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updatePublicInventory`, undo: async () => {
        await ((next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_inventory_enabled: next }),
      }))(!next);
        await (refreshSettings)();
      } });
    },
  });

  return <>
    <SettingsRow label="Public inventory" helper="Show the public catalogue. Turning this off keeps your inventory data.">
      <div className="@container grid gap-3"><Badge label="" tone={publicInventoryEnabled ? "success" : "neutral"}>{publicInventoryEnabled ? "On" : "Off"}</Badge>
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={publicInventoryEnabled}
          disabled={loading || updatePublicInventory.isPending} onChange={event => updatePublicInventory.mutate(event.target.checked)} />Show public inventory</label>
        {updatePublicInventory.error ? <p role="alert" className="text-sm text-danger">{updatePublicInventory.error.message}</p> : null}
      </div>
    </SettingsRow>
    <MakerspacePublicSiteSettings makerspace={settings ?? makerspace} loading={loading} />
  </>;
}
