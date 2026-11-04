import { useMutation } from "@tanstack/react-query";
import { Archive, Clock, Undo2 } from "lucide-react";
import { memberRequest, staffRequest } from "../../lib/api";

/** X38 (`notifications.inbox_snooze`): snooze for a day, archive, or bring a message back. */
export function InboxRowActions({ path, id, member, archived, onChanged }: {
  path: string; id: number; member: boolean; archived: boolean; onChanged: () => void;
}) {
  const send = member ? memberRequest : staffRequest;
  const change = useMutation({ mutationFn: ({ action, body }: { action: string; body?: unknown }) =>
    send(`${path}/${id}/${action}`, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) }), onSuccess: onChanged });
  const tomorrow = () => new Date(Date.now() + 24 * 3600_000).toISOString();
  if (archived) return <button type="button" className="desk-button inline-flex items-center gap-1" disabled={change.isPending}
    onClick={() => change.mutate({ action: "restore" })}><Undo2 aria-hidden="true" className="size-4" />Restore</button>;
  return <>
    <button type="button" className="desk-button inline-flex items-center gap-1" disabled={change.isPending}
      onClick={() => change.mutate({ action: "snooze", body: { until: tomorrow() } })}><Clock aria-hidden="true" className="size-4" />Snooze a day</button>
    <button type="button" className="desk-button inline-flex items-center gap-1" disabled={change.isPending}
      onClick={() => change.mutate({ action: "archive" })}><Archive aria-hidden="true" className="size-4" />Archive</button>
  </>;
}
