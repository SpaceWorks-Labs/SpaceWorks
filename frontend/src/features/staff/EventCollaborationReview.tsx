import { plural, t } from "@lingui/core/macro";
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
  const callout: CalloutProps | undefined = invited ? { size: "banner", tone: "warn", lead: plural(invited, { one: "# invitation to co-host an event.", other: "# invitations to co-host an event." }), action: { label: t`Review`, onClick: () => setOpen(true) } } : undefined;
  const detail = <>
    {total && !invited ? <button className="desk-button mt-6" type="button" onClick={() => setOpen(true)}>{t`Review collaborations`}</button> : null}
    {open ? <DetailLayout presentation="drawer" open onClose={() => setOpen(false)} title={t`Event collaborations`} state={{ status: "ready" }}
      main={<><CollaborationInbox makerspaceId={makerspaceId} /><EventSeriesCollaborationInbox makerspaceId={makerspaceId} /></>} /> : null}
  </>;
  return { callout, detail };
}
