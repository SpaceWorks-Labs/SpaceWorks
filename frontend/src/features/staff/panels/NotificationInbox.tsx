import { PersonalInbox } from "../../notifications/PersonalInbox";
import { BroadcastComposer } from "../BroadcastComposer";
import type { Makerspace } from "./shared";
import { useState } from "react";
import { Modal } from "../../../components/ui";

export function NotificationInbox({ makerspace, canManageMembers = false }: { makerspace: Makerspace; canManageMembers?: boolean }) {
  const [compose, setCompose] = useState(false);
  const canBroadcast = canManageMembers && makerspace.enabled_features?.includes("membership.broadcasts");
  return <>
    <PersonalInbox makerspaceId={makerspace.id} announcement={canBroadcast ? { label: "Send announcement", onClick: () => setCompose(true) } : undefined} />
    {canBroadcast ? <Modal open={compose} onClose={() => setCompose(false)} title="Send announcement">
      {compose ? <BroadcastComposer makerspaceId={makerspace.id} /> : null}
    </Modal> : null}
  </>;
}
