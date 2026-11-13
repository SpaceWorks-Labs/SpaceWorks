import { t } from "@lingui/core/macro";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog, type ReasonSpec } from "./ActionDialog";
import { useSpaceAction, type HealthCard, type SpaceAction } from "./spacesApi";

export type SimpleAction = "suspend" | "unsuspend" | "read-only" | "read-only/lift" | "schedule/cancel" | "archive" | "unarchive";

const getReason = (): ReasonSpec => ({ label: t`Reason`, min: 10, max: 500 });

type Copy = { title: string; message: (card: HealthCard) => string; confirm: string; done: string; danger?: boolean; reason?: boolean };
const getCopy = (): Record<SimpleAction, Copy> => ({
  suspend: { title: t`Suspend this space`, confirm: t`Suspend space`, done: t`Space suspended.`, danger: true, reason: true,
    message: card => t`${card.name} goes offline for everyone: members and staff see a "This space is paused" page. The reason is recorded in the audit log and is never shown to them.` },
  unsuspend: { title: t`Unblock this space`, confirm: t`Unblock space`, done: t`Space unblocked.`,
    message: card => t`${card.name} opens again for its members and staff.` },
  "read-only": { title: t`Make this space read-only`, confirm: t`Make read-only`, done: t`Space is now read-only.`, reason: true,
    message: card => t`People in ${card.name} can still view and export, but nothing new can be created. Staff see the reason in a banner.` },
  "read-only/lift": { title: t`Lift read-only`, confirm: t`Lift read-only`, done: t`Read-only lifted.`,
    message: card => t`${card.name} can create and change records again.` },
  "schedule/cancel": { title: t`Cancel the schedule`, confirm: t`Cancel schedule`, done: t`Schedule cancelled.`,
    message: card => t`The scheduled archive and purge of ${card.name} will not run.` },
  archive: { title: t`Archive this space now`, confirm: t`Archive now`, done: t`Space archived.`, danger: true,
    message: card => t`${card.name} is taken offline and kept for its retention period. You can unarchive it until it is purged.` },
  unarchive: { title: t`Unarchive this space`, confirm: t`Unarchive`, done: t`Space unarchived.`,
    message: card => t`${card.name} comes back online with its data as it was archived.` },
});

/** The controls that take nothing but a confirmation (and a reason, for suspend and read-only). */
export function SimpleSpaceDialog({ card, action, onClose }: { card: HealthCard; action: SimpleAction; onClose: () => void }) {
  const copy = getCopy()[action];
  const mutation = useSpaceAction(card.id, action as SpaceAction, () => { toast(copy.done); onClose(); });
  return <ActionDialog title={copy.title} message={copy.message(card)} confirmLabel={copy.confirm} tone={copy.danger ? "danger" : "default"}
    reason={copy.reason ? getReason() : undefined} pending={mutation.isPending} error={mutation.error} onCancel={onClose}
    onSubmit={reason => mutation.mutate(copy.reason ? { reason } : {})} />;
}
