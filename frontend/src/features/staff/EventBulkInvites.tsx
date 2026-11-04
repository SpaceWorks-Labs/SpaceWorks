import { useId, useState } from "react";
import { useBulkEventInvites } from "./eventCommunicationsApi";
import { eventErrorText } from "./eventUi";

export function EventBulkInvites({ eventId, disabled }: { eventId: number; disabled: boolean }) {
  const [text, setText] = useState("");
  const helpId = useId();
  const invite = useBulkEventInvites(eventId);
  const emails = text.split(/[\s,;]+/).filter(Boolean);
  return <form className="grid gap-3" aria-label="Bulk email invitations" onSubmit={(e) => { e.preventDefault(); invite.mutate(emails, { onSuccess: () => setText("") }); }}>
    <label className="grid gap-1 text-sm font-semibold text-ink">Invite by email (up to 200)
      <textarea className="desk-input min-h-28 w-full min-w-0 font-normal" aria-describedby={helpId} value={text} disabled={disabled} onChange={(e) => setText(e.target.value)} />
    </label>
    <p id={helpId} className="text-sm text-muted">Invitation emails link to the event. Participants sign in and verify their email; no admission code is emailed.</p>
    <button className="desk-button justify-self-start" type="submit" disabled={disabled || invite.isPending || !emails.length || emails.length > 200}>{invite.isPending ? "Adding invitations…" : "Add and email invitations"}</button>
    {invite.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(invite.error)}</p> : null}
    {invite.data ? <p role="status" className="text-sm text-success-ink">{invite.data.created} invitations added.</p> : null}
  </form>;
}
