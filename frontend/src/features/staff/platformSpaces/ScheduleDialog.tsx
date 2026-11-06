import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { useSpaceAction, type HealthCard, type ScheduleBody } from "./spacesApi";

/**
 * An active space is archived on a chosen date and purged `grace` days later. An archived space
 * has no archive date to choose: its purge falls due `grace` days from now. Every schedule ends in
 * a purge, so the slug is typed out to confirm, as in PurgeDialog.
 */
export function ScheduleDialog({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const archived = card.archived_at !== null;
  const [archiveOn, setArchiveOn] = useState("");
  const [grace, setGrace] = useState("90");
  const [note, setNote] = useState("");
  const [slug, setSlug] = useState("");
  const mutation = useSpaceAction(card.id, "schedule", () => { toast(archived ? "Purge scheduled." : "Archive and purge scheduled."); onClose(); });
  const graceDays = Number(grace);
  const when = archiveOn ? new Date(archiveOn) : null;
  const dateOk = archived || (when !== null && !Number.isNaN(when.getTime()) && when.getTime() > Date.now());
  const canSubmit = dateOk && Number.isInteger(graceDays) && graceDays >= 1 && graceDays <= 3650 && note.length <= 500 && slug.trim() === card.slug;
  return <ActionDialog title={archived ? "Schedule the purge" : "Schedule archive & purge"} tone="danger"
    confirmLabel={archived ? "Schedule purge" : "Schedule"} pending={mutation.isPending} error={mutation.error} canSubmit={canSubmit}
    message={archived
      ? `${card.name} is archived. Its data is deleted for good when the grace period ends. You can cancel the schedule until then.`
      : `${card.name} is archived on the date you choose and its data is deleted for good when the grace period after that ends. Space Managers get reminders.`}
    onCancel={onClose}
    onSubmit={() => mutation.mutate({ archive_on: archived || !when ? null : when.toISOString(), purge_grace_days: graceDays, note: note.trim(), confirm_slug: slug.trim() } satisfies ScheduleBody)}>
    {!archived ? <Field label="Archive on" hint="Your local time. It must be in the future.">
      <input className="desk-input" type="datetime-local" value={archiveOn} onChange={event => setArchiveOn(event.target.value)} />
    </Field> : null}
    <Field label="Grace period before the purge (days)" hint="Between 1 and 3650 days.">
      <input className="desk-input" type="number" min={1} max={3650} inputMode="numeric" value={grace} onChange={event => setGrace(event.target.value)} />
    </Field>
    <Field label="Note (optional)" hint="Shown to other platform operators, not to the space.">
      <textarea className="desk-input min-h-20" maxLength={500} value={note} onChange={event => setNote(event.target.value)} />
    </Field>
    <Field label={`Type ${card.slug} to confirm`}>
      <input className="desk-input" autoComplete="off" autoCapitalize="none" spellCheck={false} value={slug} onChange={event => setSlug(event.target.value)} />
    </Field>
  </ActionDialog>;
}
