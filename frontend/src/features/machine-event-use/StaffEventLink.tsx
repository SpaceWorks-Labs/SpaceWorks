import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { eventUseKeys, fetchLink, saveLink, type UseKind } from "./api";

function problem(error: unknown) {
  if (error instanceof StructuredApiError && error.code === "cost_approved") {
    return t`The organiser approved this cost for the event. Withdraw the approval on the event page first.`;
  }
  return t`Couldn't change the event. Try again.`;
}

/** The area manager's event link for one session or job: set, change or clear it (audited with before and after). */
export function StaffEventLink({ makerspaceId, kind, id }: { makerspaceId: number; kind: UseKind; id: number }) {
  const client = useQueryClient();
  const key = eventUseKeys.link(makerspaceId, kind, id);
  const link = useQuery({ queryKey: key, queryFn: () => fetchLink(makerspaceId, kind, id), retry: false });
  const save = useMutation({ mutationFn: (eventId: number | null) => saveLink(makerspaceId, kind, id, eventId),
    onSuccess: data => { client.setQueryData(key, data); } });
  if (link.isError) return <p role="status" className="text-sm text-muted">{t`Only machine-time bookings, sessions and jobs can be logged for an event.`}</p>;
  if (!link.data) return null;
  const { event, options, locked } = link.data;
  return <div className="grid gap-2">
    <Field label={t`Logged for event`} hint={locked ? t`The organiser approved this cost, so the event is locked.` : undefined}>
      <select className="desk-input min-h-11 w-full" value={event ? String(event.id) : ""} disabled={locked || save.isPending}
        onChange={change => save.mutate(change.target.value ? Number(change.target.value) : null)}>
        <option value="">{t`Not for an event`}</option>
        {event && !options.some(row => row.id === event.id) ? <option value={String(event.id)}>{event.title}</option> : null}
        {options.map(row => <option key={row.id} value={String(row.id)}>{row.title}</option>)}
      </select>
    </Field>
    {save.isError ? <p role="alert" className="text-sm text-danger">{problem(save.error)}</p> : null}
  </div>;
}
