import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";

import { ErrorBlock } from "../../components/ui";
import { CONNECTABLE } from "./channelCatalog";
import { useEndpoints, usePreferences, useVerifyChallenge } from "./channelsApi";
import { ChannelDeliveryLog } from "./ChannelDeliveryLog";
import { ChannelPreferences } from "./ChannelPreferences";
import { connectedChannels, PersonalChannels } from "./PersonalChannels";
import { slackInstallKey, useCompleteSlackInstall } from "./SlackInstallation";

/** Return parameters an OAuth provider sign-in (Slack, Discord, Mattermost) lands back with. */
const RETURN_KEYS = ["notify_challenge", "code", "state"] as const;

/**
 * A person's own notification setup in one makerspace, shared by the staff console and the
 * member portal: connect chat accounts, choose channels per category, see recent deliveries.
 * Offered channels come from the server's `available_channels`, which already applies the
 * space's channel switches, modules and features.
 */
export function MyNotificationSettings({ makerspaceId, member = false }: { makerspaceId: number; member?: boolean }) {
  const preferences = usePreferences(makerspaceId, member);
  const endpoints = useEndpoints(makerspaceId, member);
  const verify = useVerifyChallenge(makerspaceId, member);
  const install = useCompleteSlackInstall(makerspaceId);
  const [search, setSearch] = useSearchParams();
  const handled = useRef(false);
  const challengeId = Number(search.get("notify_challenge"));
  useEffect(() => {
    if (handled.current || !challengeId) return;
    handled.current = true;
    const proof = { code: search.get("code") ?? undefined, state: search.get("state") ?? undefined };
    if (!member && proof.state && sessionStorage.getItem(slackInstallKey(makerspaceId)) === proof.state) install.mutate(proof);
    else verify.mutate({ challengeId, ...proof });
    const next = new URLSearchParams(search);
    RETURN_KEYS.forEach(key => next.delete(key));
    setSearch(next, { replace: true });
  }, [challengeId, search, setSearch, verify, install, makerspaceId, member]);
  if (preferences.isLoading) return <p className="text-sm text-muted">Loading your notification settings…</p>;
  if (preferences.error || !preferences.data) return <ErrorBlock error={preferences.error ?? new Error("Couldn't load your notification settings.")}
    onRetry={() => { void preferences.refetch(); }} />;
  const rows = preferences.data.preferences;
  const offered = new Set(rows.flatMap(row => row.available_channels ?? []));
  const chat = CONNECTABLE.filter(channel => offered.has(channel));
  return <div className="grid min-w-0 gap-6">
    {verify.isError ? <p role="alert" className="text-sm text-danger">Couldn't finish connecting: {verify.error.message}</p> : null}
    {verify.isSuccess ? <p role="status" className="text-sm text-muted">Connected.</p> : null}
    {install.isError ? <p role="alert">Couldn't install Slack: {install.error.message}</p> : null}
    {install.isSuccess ? <p role="status">Slack app installed. You can now enable personal messages in channel settings.</p> : null}
    <section aria-label="Connected channels" className="grid min-w-0 gap-3">
      <h3 className="title-section">Your channels</h3>
      <PersonalChannels makerspaceId={makerspaceId} channels={chat} member={member} />
    </section>
    <section aria-label="Notification choices" className="grid min-w-0 gap-3">
      <h3 className="title-section">What goes where</h3>
      <ChannelPreferences key={JSON.stringify(rows)} makerspaceId={makerspaceId} preferences={rows} member={member}
        connected={connectedChannels(endpoints.data?.results)} />
    </section>
    <ChannelDeliveryLog makerspaceId={makerspaceId} member={member} title="Recent deliveries" />
  </div>;
}
