import { useState } from "react";
import { DetailLayout } from "../../components/layouts";
import type { CalloutProps } from "../../components/ui";
import { CollaborationInbox } from "./CollaborationInbox";
import { useCollaborationInbox } from "./eventCollaborationsApi";
import { EventSeriesCollaborationInbox, useSeriesCollaborationInbox } from "./EventSeriesCollaborationInbox";

/** Keep the existing inbox queries and hand their presentation to the list layout slots. */
export function useEventCollaborationReview(makerspaceId: number) {
  const [open, setOpen] = useState(false);
  const inbox = useCollaborationInbox(makerspaceId);
  const series = useSeriesCollaborationInbox(makerspaceId);
  const invited = [...(inbox.data ?? []), ...(series.data ?? [])].filter(row => row.status === "invited").length;
  const total = (inbox.data?.length ?? 0) + (series.data?.length ?? 0);
  const callout: CalloutProps | undefined = invited ? { size: "banner", tone: "warn", lead: `${invited} ${invited === 1 ? "invitation" : "invitations"} to co-host an event.`, action: { label: "Review", onClick: () => setOpen(true) } } : undefined;
  const detail = <>
    {total && !invited ? <button className="desk-button mt-6" type="button" onClick={() => setOpen(true)}>Review collaborations</button> : null}
    {open ? <DetailLayout presentation="drawer" open onClose={() => setOpen(false)} title="Event collaborations" state={{ status: "ready" }}
      main={<><CollaborationInbox makerspaceId={makerspaceId} /><EventSeriesCollaborationInbox makerspaceId={makerspaceId} /></>} /> : null}
  </>;
  return { callout, detail };
}
