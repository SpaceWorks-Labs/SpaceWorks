import { t } from "@lingui/core/macro";
import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import { SettingsRow } from "../../components/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./panels/shared";

export function MakerspaceBookingSettings({ makerspace, settings, loading }: {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
}) {
  const queryClient = useQueryClient();
  const enabled = settings?.booking_requester_notifications_enabled
    ?? makerspace.booking_requester_notifications_enabled
    ?? false;
  const update = useMutation({
    mutationFn: (next: boolean) => staffRequest<Makerspace>("/admin/makerspaces/" + makerspace.id, {
      method: "PATCH",
      body: JSON.stringify({ booking_requester_notifications_enabled: next }),
    }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-update`),
    onSuccess: async (_data, next) => {
      await (async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] }),
        queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
        queryClient.invalidateQueries({ queryKey: ["bookings", makerspace.id] }),
      ]);
    })();
      toast((next ? t`Booking requester emails turned on.` : t`Booking requester emails turned off.`), { undoKey: `settings-${makerspace.id}-update`, undo: async () => {
        await ((next: boolean) => staffRequest<Makerspace>("/admin/makerspaces/" + makerspace.id, {
      method: "PATCH",
      body: JSON.stringify({ booking_requester_notifications_enabled: next }),
    }))(!next);
        await (async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] }),
        queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
        queryClient.invalidateQueries({ queryKey: ["bookings", makerspace.id] }),
      ]);
    })();
      } });
    },
  });

  return (
    <SettingsRow label={t`Booking requester emails`} helper={t`Set the default for booking submitted, confirmed, and rejected emails. Each space may inherit or override this setting.`}><div className="@container grid min-w-0 gap-4">
      <div className="grid min-w-0 gap-3  md:items-start">
        <div className="grid min-w-0 max-w-2xl gap-2">
          <div className="flex flex-wrap items-center gap-2">

            <Badge label="" tone={enabled ? "success" : "neutral"}>{enabled ? t`On` : t`Off`}</Badge>
          </div>

          {update.error ? <p className="text-sm text-danger" role="alert">{update.error.message}</p> : null}
        </div>
        <label className="min-h-11 flex min-w-0 items-start gap-3 text-sm text-ink md:justify-self-end">
          <input className="mt-1 h-4 w-4" type="checkbox" checked={enabled} disabled={loading || update.isPending} onChange={(event) => update.mutate(event.target.checked)} />
          <span className="font-semibold">{t`Email booking requesters`}</span>
        </label>
      </div>
    </div></SettingsRow>
  );
}
