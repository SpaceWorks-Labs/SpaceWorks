import { toast } from "../../../components/ui/toastStore";
import { ActionDialog, type ReasonSpec } from "./ActionDialog";
import { useSpaceAction, type HealthCard, type SpaceAction } from "./spacesApi";

export type SimpleAction = "suspend" | "unsuspend" | "read-only" | "read-only/lift" | "schedule/cancel" | "archive" | "unarchive";

const REASON: ReasonSpec = { label: "Reason", min: 10, max: 500 };

type Copy = { title: string; message: (card: HealthCard) => string; confirm: string; done: string; danger?: boolean; reason?: boolean };
const COPY: Record<SimpleAction, Copy> = {
  suspend: { title: "Suspend this space", confirm: "Suspend space", done: "Space suspended.", danger: true, reason: true,
    message: card => `${card.name} goes offline for everyone: members and staff see a "This space is paused" page. The reason is recorded in the audit log and is never shown to them.` },
  unsuspend: { title: "Unblock this space", confirm: "Unblock space", done: "Space unblocked.",
    message: card => `${card.name} opens again for its members and staff.` },
  "read-only": { title: "Make this space read-only", confirm: "Make read-only", done: "Space is now read-only.", reason: true,
    message: card => `People in ${card.name} can still view and export, but nothing new can be created. Staff see the reason in a banner.` },
  "read-only/lift": { title: "Lift read-only", confirm: "Lift read-only", done: "Read-only lifted.",
    message: card => `${card.name} can create and change records again.` },
  "schedule/cancel": { title: "Cancel the schedule", confirm: "Cancel schedule", done: "Schedule cancelled.",
    message: card => `The scheduled archive and purge of ${card.name} will not run.` },
  archive: { title: "Archive this space now", confirm: "Archive now", done: "Space archived.", danger: true,
    message: card => `${card.name} is taken offline and kept for its retention period. You can unarchive it until it is purged.` },
  unarchive: { title: "Unarchive this space", confirm: "Unarchive", done: "Space unarchived.",
    message: card => `${card.name} comes back online with its data as it was archived.` },
};

/** The controls that take nothing but a confirmation (and a reason, for suspend and read-only). */
export function SimpleSpaceDialog({ card, action, onClose }: { card: HealthCard; action: SimpleAction; onClose: () => void }) {
  const copy = COPY[action];
  const mutation = useSpaceAction(card.id, action as SpaceAction, () => { toast(copy.done); onClose(); });
  return <ActionDialog title={copy.title} message={copy.message(card)} confirmLabel={copy.confirm} tone={copy.danger ? "danger" : "default"}
    reason={copy.reason ? REASON : undefined} pending={mutation.isPending} error={mutation.error} onCancel={onClose}
    onSubmit={reason => mutation.mutate(copy.reason ? { reason } : {})} />;
}
