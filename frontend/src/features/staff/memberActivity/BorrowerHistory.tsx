import { t } from "@lingui/core/macro";
import { useId, useState } from "react";

import { MemberActivitySection } from "./MemberActivitySection";

/**
 * Open item A26 (IN7): the borrower's other loans, charges and restriction state, opened in place
 * from a request's detail drawer. Reuses the member 360, so rows stay limited to areas the viewer
 * manages and the server answers for account-only borrowers too.
 */
export function BorrowerHistoryToggle({ makerspaceId, userId }: { makerspaceId: number; userId: number }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return <section className="grid min-w-0 gap-2">
    <button type="button" className="desk-button w-fit" aria-expanded={open} aria-controls={panelId}
      onClick={() => setOpen(value => !value)}>{open ? t`Hide borrower history` : t`Borrower history`}</button>
    <div id={panelId} hidden={!open} className="min-w-0">{open ? <MemberActivitySection makerspaceId={makerspaceId} userId={userId} /> : null}</div>
  </section>;
}
