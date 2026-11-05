import { useMutation, useQueryClient } from "@tanstack/react-query";

import { SettingsRow } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./StaffPanels";

type Props = { makerspace: Makerspace; settings?: Makerspace; loading: boolean };

/** #192: "Hide from the platform" is its own setting, independent of a custom domain.
 *  The server writes it through the settings authority and audits it as `settings.changed`. */
export function MakerspaceDirectoryVisibility({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const hidden = settings?.hidden_from_central_directory ?? makerspace.hidden_from_central_directory ?? false;
  const save = useMutation({
    mutationFn: (next: boolean) => staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ hidden_from_central_directory: next }),
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      void queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      void queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    },
  });
  return <SettingsRow label="Hide from the platform"
    helper="Leave this space out of the platform directory, Discover, cross-space search and the shared event listings.">
    <div className="grid min-w-0 max-w-xl gap-2">
      <label className="flex min-h-11 items-start gap-3 text-sm text-ink">
        <input className="mt-1 h-4 w-4" type="checkbox" checked={hidden} disabled={loading || save.isPending}
          onChange={event => save.mutate(event.target.checked)} />
        <span>
          <span className="font-semibold">Hide this space from the platform</span>
          <span className="block text-muted">
            Its own address{makerspace.frontend_domain ? ` (${makerspace.frontend_domain})` : ` (/m/${makerspace.slug})`} keeps
            working for members and visitors who have the link. The platform operator still sees it.
          </span>
        </span>
      </label>
      {save.isPending ? <p role="status" className="text-sm text-muted">Saving…</p> : null}
      {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    </div>
  </SettingsRow>;
}
