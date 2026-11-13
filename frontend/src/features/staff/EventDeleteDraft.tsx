import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ConfirmDialog } from "../../components/ui";
import { toast } from "../../components/ui/toastStore";
import { staffRequest, StructuredApiError } from "../../lib/api";
import { eventErrorText } from "./eventUi";
import { EVENT_DETAIL_PATH, staffPath, type StaffEvent } from "./eventsApiTypes";
import { useEventInvalidation } from "./eventsApi";

/**
 * Delete an empty draft (parity E-F3, B9). The server refuses (409) once the event has been published or holds a
 * registration, an order or a charge; those are cancelled instead so their history stays on the record.
 */
export function EventDeleteDraft({ event, makerspaceId, onDeleted }: { event: StaffEvent; makerspaceId: number; onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const invalidate = useEventInvalidation(makerspaceId);
  const remove = useMutation({
    mutationFn: () => staffRequest<void>(staffPath(EVENT_DETAIL_PATH, { id: event.id }), { method: "DELETE" }),
    onSuccess: async () => { setOpen(false); toast(t`Draft “${event.title}” deleted.`); await invalidate(); onDeleted(); },
  });
  if (event.status !== "draft") return null;
  const refused = remove.error instanceof StructuredApiError && remove.error.status === 409;
  const signedUp = Object.values(event.registration_counts ?? {}).reduce((sum, count) => sum + count, 0);
  return <section className="grid gap-2 rounded-xl border border-danger-line bg-panel p-4" aria-labelledby={`delete-draft-${event.id}`}>
    <h3 id={`delete-draft-${event.id}`} className="font-semibold text-ink">{t`Delete this draft`}</h3>
    <p className="text-sm text-muted">{signedUp
      ? t`People have already signed up, so this draft can no longer be deleted. Cancel it instead.`
      : t`Removes the draft and its cover for good. Only a draft nobody has signed up for, ordered or paid for can be deleted.`}</p>
    {remove.error ? <p role="alert" className="text-sm text-danger">{refused ? t`This draft now has sign-ups, orders or charges, so it can't be deleted. Cancel it instead.` : eventErrorText(remove.error)}</p> : null}
    <button type="button" className="desk-button-danger-outline justify-self-start" disabled={signedUp > 0 || remove.isPending} onClick={() => { remove.reset(); setOpen(true); }}>{t`Delete draft…`}</button>
    <ConfirmDialog open={open} tone="danger" title={t`Delete “${event.title}”?`} pending={remove.isPending}
      message={t`The draft, its settings and its cover are removed. This cannot be undone.`} confirmLabel={t`Delete draft`} cancelLabel={t`Keep draft`}
      onCancel={() => setOpen(false)} onConfirm={() => remove.mutate(undefined, { onError: () => setOpen(false) })} />
  </section>;
}
