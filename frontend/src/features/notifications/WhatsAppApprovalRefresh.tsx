import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { Channel, WhatsAppTemplate } from "./channelsApi";

/** Approval is provider-owned. Refresh saved bindings without rotating credentials. */
export function WhatsAppApprovalRefresh({ makerspaceId, disabled, onRefresh }: {
  makerspaceId: number; disabled: boolean; onRefresh: (templates: WhatsAppTemplate[]) => void;
}) {
  const client = useQueryClient();
  const refresh = useMutation({
    mutationFn: async () => {
      const base = `/integrations/makerspace/${makerspaceId}`;
      const result = await staffRequest<{ checked: number; approved: number; unavailable: number }>(
        `${base}/whatsapp/twilio/templates/refresh`, { method: "POST", body: "{}" });
      const saved = await staffRequest<Channel>(`${base}/channels/whatsapp`);
      onRefresh(saved.templates);
      return result;
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["notify-contract", makerspaceId, "channels"] }),
  });
  return <div className="grid gap-2">
    <p className="text-sm text-muted">Save template bindings, then refresh their approval from Twilio before connecting or testing.</p>
    <button className="desk-button" type="button" disabled={disabled || refresh.isPending} onClick={() => refresh.mutate()}>
      {refresh.isPending ? "Refreshing approval…" : "Refresh approval"}</button>
    {refresh.data ? <p role="status">{refresh.data.approved} of {refresh.data.checked} templates approved.
      {refresh.data.unavailable ? " Some approvals could not be checked. Try refreshing again." : ""}</p> : null}
    {refresh.error ? <p role="alert">Couldn't refresh approval: {refresh.error.message}</p> : null}
  </div>;
}
