import { t } from "@lingui/core/macro";
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

/** The borrower-name opt-in (#80). The page switch itself lives in Settings › Public stats (#170). */
export function MakerspacePublicStatsSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const showHolderNames =
    settings?.public_stats_show_holder_names ?? makerspace.public_stats_show_holder_names ?? false;

  const invalidateSettings = () => {
    queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
    queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
  };
  const patchHolderNames = (next: boolean) =>
    staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH",
      body: JSON.stringify({ public_stats_show_holder_names: next }),
    });
  const updateHolderNames = useMutation({
    mutationFn: patchHolderNames,
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updateHolderNames`),
    onSuccess: async (_data, next) => {
      await invalidateSettings();
      toast(t`Public borrower names turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updateHolderNames`, undo: async () => {
        await patchHolderNames(!next);
        await invalidateSettings();
      } });
    },
  });

  return <SettingsRow label={t`Public borrower names`} helper="When on, the “Out right now” list publishes the borrower’s name on the public stats page. When off, every borrower is shown as Member. Nothing else on the page ever carries a name.">
    <div className="@container grid gap-3"><Badge label="" tone={showHolderNames ? "warn" : "neutral"}>{showHolderNames ? t`On` : t`Off`}</Badge>
      <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={showHolderNames}
        disabled={loading || updateHolderNames.isPending} onChange={event => updateHolderNames.mutate(event.target.checked)} />{t`Publish borrower names publicly`}</label>
      {updateHolderNames.error ? <p role="alert" className="text-sm text-danger">{updateHolderNames.error.message}</p> : null}
    </div>
  </SettingsRow>;
}
