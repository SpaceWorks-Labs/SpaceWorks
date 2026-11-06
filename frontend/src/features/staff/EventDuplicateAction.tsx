import { t } from "@lingui/core/macro";
import { useState } from "react";
import { createPortal } from "react-dom";

import { Modal } from "../../components/ui";
import type { StaffEvent } from "./eventsApi";
import { useDuplicateEvent } from "./eventToolsApi";
import { eventErrorText } from "./eventUi";

export function EventDuplicateAction({ event, makerspaceId }: { event: StaffEvent; makerspaceId: number }) {
  const [open, setOpen] = useState(false);
  const [attachSeries, setAttachSeries] = useState(false);
  const duplicate = useDuplicateEvent(makerspaceId, event.id);
  return <>
    <button className="desk-button w-fit" type="button" onClick={() => { duplicate.reset(); setAttachSeries(false); setOpen(true); }}>{t`Duplicate event`}</button>
    {createPortal(<Modal open={open} title={t`Duplicate event`} onClose={() => { if (!duplicate.isPending) setOpen(false); }}>
      <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); duplicate.mutate(attachSeries, { onSuccess: () => setOpen(false) }); }}>
        <p className="text-sm text-muted">{t`Create a draft copy of the event, ticket types, registration form and feedback questions. Review its dates before publishing.`}</p>
        {event.series_summary ? <label className="flex min-h-11 items-center gap-3 rounded-xl border border-line p-4 text-sm text-ink has-checked:border-accent has-checked:bg-accent-soft"><input type="checkbox" checked={attachSeries} onChange={(e) => setAttachSeries(e.target.checked)} disabled={duplicate.isPending} />{t`Attach to ${event.series_summary.title} (requires series management permission)`}</label> : null}
        {duplicate.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(duplicate.error)}</p> : null}
        <div className="flex justify-end"><button className="desk-button-primary" type="submit" disabled={duplicate.isPending}>{duplicate.isPending ? t`Duplicating…` : t`Create draft copy`}</button></div>
      </form>
    </Modal>, document.body)}
  </>;
}
