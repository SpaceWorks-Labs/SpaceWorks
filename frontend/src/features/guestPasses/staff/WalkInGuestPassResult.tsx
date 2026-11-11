import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { formatDateTime } from "../../../lib/format";
import { StructuredApiError } from "../../../lib/api";
import { guestErrorText, guestKeys, guestStaffApi } from "../api";

/** The walk-in answer when the space registers non-members on a guest pass (decision 223 i). */
export type WalkInGuestPass = {
  user_id: number; display_name: string; username: string; is_walk_in: boolean;
  guest_pass_id: number; guest_pass_valid_until: string; waiver_accepted: boolean;
};

/** Shows the day's pass and lets the desk stamp the waiver the guest accepted in person. */
export function WalkInGuestPassResult({ makerspaceId, result }: { makerspaceId: number; result: WalkInGuestPass }) {
  const client = useQueryClient();
  const stamp = useMutation({
    mutationFn: () => guestStaffApi.stampWaiver(makerspaceId, result.guest_pass_id),
    onSuccess: () => { void client.invalidateQueries({ queryKey: guestKeys.all(makerspaceId) }); },
  });
  const accepted = result.waiver_accepted || stamp.isSuccess;
  // The desk stamp needs manage_members; a handover desk without it is told who can.
  const forbidden = stamp.error instanceof StructuredApiError && stamp.error.status === 403;
  return <div className="mt-3 grid gap-2 rounded border border-line bg-surface p-3" role="status">
    <p className="text-sm font-semibold text-ink">{t`${result.display_name || result.username} has a guest pass until ${formatDateTime(result.guest_pass_valid_until)}.`}</p>
    <p className="text-sm text-muted">{t`This space registers walk-ins as guests, not members. The pass decides what they may borrow or use today.`}</p>
    {accepted ? <p className="text-sm text-success-ink">{t`Waiver accepted.`}</p> : <div className="flex flex-wrap items-center gap-3">
      <button type="button" className="desk-button min-h-11" disabled={stamp.isPending} onClick={() => stamp.mutate()}>
        {stamp.isPending ? t`Recording…` : t`Waiver accepted at the desk`}</button>
      <span className="text-xs text-muted">{t`Tick only after the guest has read and accepted the current waiver.`}</span>
    </div>}
    {stamp.error ? <p role="alert" className="text-sm text-danger">{forbidden ? t`Ask a member manager to record the waiver under Members › Guests.` : guestErrorText(stamp.error)}</p> : null}
  </div>;
}
