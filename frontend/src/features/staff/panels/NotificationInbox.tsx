import { PersonalInbox } from "../../notifications/PersonalInbox";
import { MyNotificationSettings } from "../../notifications/MyNotificationSettings";
import { BrowserAlertsToggle } from "../../notifications/BrowserAlertsToggle";
import { BroadcastComposer } from "../BroadcastComposer";
import type { Makerspace } from "./shared";
import { useState } from "react";
import { Modal, type Action } from "../../../components/ui";

export function NotificationInbox({ makerspace, canManageMembers = false }: { makerspace: Makerspace; canManageMembers?: boolean }) {
  const [compose, setCompose] = useState(false);
  // Provider returns carry signed state; the server resolves its challenge.
  const [channels, setChannels] = useState(() => new URLSearchParams(window.location.search).has("state"));
  const canBroadcast = canManageMembers && makerspace.enabled_features?.includes("membership.broadcasts");
  const myChannels: Action = { label: "My channels", icon: "Settings", onClick: () => setChannels(true) };
  const announcement: Action | undefined = canBroadcast ? { label: "Send announcement", onClick: () => setCompose(true) } : undefined;
  return <>
    {makerspace.enabled_features?.includes("notifications.web_push") ? <BrowserAlertsToggle makerspaceId={makerspace.id} /> : null}
    <PersonalInbox makerspaceId={makerspace.id} makerspaceSlug={makerspace.slug} announcement={announcement ?? myChannels}
      overflow={announcement && myChannels ? [myChannels] : undefined}
      snooze={Boolean(makerspace.enabled_features?.includes("notifications.inbox_snooze"))} />
    {canBroadcast ? <Modal open={compose} onClose={() => setCompose(false)} title="Send announcement">
      {compose ? <BroadcastComposer makerspaceId={makerspace.id} /> : null}
    </Modal> : null}
    <Modal open={channels} onClose={() => setChannels(false)} title="My notification channels" size="xl">
      {channels ? <MyNotificationSettings makerspaceId={makerspace.id} /> : null}
    </Modal>
  </>;
}
