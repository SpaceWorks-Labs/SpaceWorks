import { t } from "@lingui/core/macro";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "../../staff/platformSpaces/ActionDialog";
import { REASON_REQUIRED, useReviewDecision, type ReviewDecision, type ReviewQueueRow } from "./reviewApi";

export const decisionLabels = (): Record<ReviewDecision, string> => ({
  approve: t`Approve`, request_changes: t`Request changes`, decline: t`Decline`, suspend: t`Suspend`, reactivate: t`Reactivate`,
});

function copy(decision: ReviewDecision, name: string) {
  switch (decision) {
    case "approve": return { done: t`${name} approved.`, title: t`Approve ${name}?`, message: t`The organization can publish its public page, link spaces and invite people. The applicant is told.` };
    case "request_changes": return { done: t`Changes requested from ${name}.`, title: t`Ask ${name} for changes`, message: t`The applicant sees your note on their status page and can resubmit once they have made the changes.` };
    case "decline": return { done: t`${name} declined.`, title: t`Decline ${name}?`, message: t`The organization is closed and its web address stays reserved for 30 days. The applicant sees your reason.` };
    case "suspend": return { done: t`${name} suspended.`, title: t`Suspend ${name}?`, message: t`Its public page goes offline and it takes no new links or invitations. Members keep their data. You can reactivate it later.` };
    case "reactivate": return { done: t`${name} reactivated.`, title: t`Reactivate ${name}?`, message: t`The organization returns to approved standing and its public page comes back if it is published.` };
  }
}

/** One decision with its consequence, a reason where the server needs one, and the step-up re-check on submit. */
export function ReviewDecisionDialog({ row, decision, onClose, onDone = onClose }: {
  row: ReviewQueueRow; decision: ReviewDecision; onClose: () => void; onDone?: () => void;
}) {
  const mutation = useReviewDecision(row.id);
  const required = REASON_REQUIRED.has(decision);
  const { title, message, done } = copy(decision, row.name);
  return <ActionDialog title={title} confirmLabel={decisionLabels()[decision]} pending={mutation.isPending} error={mutation.error}
    tone={decision === "decline" || decision === "suspend" ? "danger" : "default"} onCancel={onClose}
    message={<><p>{message}</p><p className="mt-2">{t`You may be asked to confirm it's you before this is saved.`}</p></>}
    reason={{ label: required ? t`Reason (shown to the applicant)` : t`Note (optional, shown to the applicant)`, min: required ? 1 : 0, max: 2000,
      hint: required ? t`Say what happened and, where it helps, what to do next.` : undefined }}
    onSubmit={reason => mutation.mutate({ decision, reason }, { onSuccess: () => {
      toast(done); onDone();
    } })} />;
}
