import { PersonalInbox } from "../../notifications/PersonalInbox";
import { MyNotificationSettings } from "../../notifications/MyNotificationSettings";
import { BroadcastComposer } from "../BroadcastComposer";
import type { Makerspace } from "./shared";
import { useState } from "react";
import { Modal, type Action } from "../../../components/ui";

export function NotificationInbox({ makerspace, canManageMembers = false }: { makerspace: Makerspace; canManageMembers?: boolean }) {
  const [compose, setCompose] = useState(false);
  // A provider sign-in (Slack, Discord, Mattermost) returns here with ?notify_challenge=…
  const [channels, setChannels] = useState(() => new URLSearchParams(window.location.search).has("notify_challenge"));
  const canBroadcast = canManageMembers && makerspace.enabled_features?.includes("membership.broadcasts");
  // Personal channels need the notifications module (the contract endpoints require it).
  const hasChannels = (makerspace.enabled_modules ?? []).includes("notifications");
  const myChannels: Action | undefined = hasChannels ? { label: "My channels", icon: "Settings", onClick: () => setChannels(true) } : undefined;
  const announcement: Action | undefined = canBroadcast ? { label: "Send announcement", onClick: () => setCompose(true) } : undefined;
  return <>
    <PersonalInbox makerspaceId={makerspace.id} makerspaceSlug={makerspace.slug} announcement={announcement ?? myChannels}
      overflow={announcement && myChannels ? [myChannels] : undefined} />
    {canBroadcast ? <Modal open={compose} onClose={() => setCompose(false)} title="Send announcement">
      {compose ? <BroadcastComposer makerspaceId={makerspace.id} /> : null}
    </Modal> : null}
    {hasChannels ? <Modal open={channels} onClose={() => setChannels(false)} title="My notification channels" size="xl">
      {channels ? <MyNotificationSettings makerspaceId={makerspace.id} /> : null}
    </Modal> : null}
  </>;
}
