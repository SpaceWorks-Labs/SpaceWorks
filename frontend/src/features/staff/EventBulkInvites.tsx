import { useState } from "react";
import { useBulkEventInvites } from "./eventCommunicationsApi";
import { eventErrorText } from "./eventUi";

export function EventBulkInvites({ eventId, disabled }: { eventId: number; disabled: boolean }) {
  const [text, setText] = useState("");
  const invite = useBulkEventInvites(eventId);
  const emails = text.split(/[\s,;]+/).filter(Boolean);
  return <form className="grid gap-2" aria-label="Bulk email invitations" onSubmit={(e) => { e.preventDefault(); invite.mutate(emails, { onSuccess: () => setText("") }); }}>
    <label>Invite by email (up to 200)<textarea className="desk-input" value={text} disabled={disabled} onChange={(e) => setText(e.target.value)} /></label>
    <p className="text-sm text-muted">Invitation emails link to the event. Participants sign in and verify their email; no admission code is emailed.</p>
    <button className="desk-button w-fit" disabled={disabled || invite.isPending || !emails.length || emails.length > 200}>{invite.isPending ? "Adding invitations…" : "Add and email invitations"}</button>
    {invite.error ? <p role="alert" className="text-danger">{eventErrorText(invite.error)}</p> : null}
    {invite.data ? <p role="status">{invite.data.created} invitations added.</p> : null}
  </form>;
}
