import { t } from "@lingui/core/macro";
import { currentSessionContext } from "../../lib/api/sessionContext";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";

export const slackInstallKey = (id: number) => `notification-slack-install:${currentSessionContext()}:${id}`;

export function useCompleteSlackInstall(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (proof: { code?: string; state?: string }) => staffRequest(
      `/integrations/makerspace/${makerspaceId}/slack/oauth/callback`, { method: "POST", body: JSON.stringify(proof) }),
    onSuccess: () => {
      sessionStorage.removeItem(slackInstallKey(makerspaceId));
      return client.invalidateQueries({ queryKey: ["notify-contract", makerspaceId] });
    },
  });
}

export function SlackInstallation({ makerspaceId, configured }: { makerspaceId: number; configured: boolean }) {
  const start = useMutation({
    mutationFn: () => staffRequest<{ connect_url: string }>(
      `/integrations/makerspace/${makerspaceId}/slack/install/start`, { method: "POST" }),
    onSuccess: data => {
      const state = new URL(data.connect_url).searchParams.get("state");
      if (state) sessionStorage.setItem(slackInstallKey(makerspaceId), state);
    },
  });
  return <div className="grid gap-2">
    <p className="text-sm text-muted">{t`Save the app credentials, then install it in Slack to verify its workspace and receive its bot token.`}</p>
    <button className="desk-button" type="button" disabled={!configured || start.isPending} onClick={() => start.mutate()}>{t`Install Slack app`}</button>
    {start.data ? <a className="desk-button" href={start.data.connect_url}>{t`Continue to Slack`}</a> : null}
    {start.error ? <p role="alert">{start.error.message}</p> : null}
  </div>;
}
