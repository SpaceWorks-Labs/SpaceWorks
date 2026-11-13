import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { UseKind } from "./api";
import { StaffEventLink } from "./StaffEventLink";

/**
 * A staff card's "Event" line: shows the event a session or job is logged for and opens the area manager's
 * editor on demand, so a list of cards does not fetch an editor per row. Hidden without a known makerspace.
 */
export function EventLinkToggle({ makerspaceId, kind, id, eventTitle, statusUnknown }: {
  makerspaceId: number | null | undefined; kind: UseKind; id: number; eventTitle?: string | null;
  /** True where the row does not say whether it can carry an event (a booking of any kind): show only the button. */
  statusUnknown?: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!makerspaceId) return eventTitle ? <p className="text-sm text-muted">{t`For event: ${eventTitle}`}</p> : null;
  return <div className="grid gap-2">
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {statusUnknown ? null : <span className="text-muted">{eventTitle ? t`For event: ${eventTitle}` : t`Not logged for an event`}</span>}
      <button type="button" className="desk-button-ghost min-h-11" aria-expanded={open} onClick={() => setOpen(value => !value)}>
        {open ? t`Done` : t`Event`}</button>
    </div>
    {open ? <StaffEventLink makerspaceId={makerspaceId} kind={kind} id={id} /> : null}
  </div>;
}
