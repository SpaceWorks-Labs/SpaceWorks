import { t } from "@lingui/core/macro";
import { StructuredApiError } from '../../lib/api';

/** E-B3/E-B4 typed refusals ({code, detail, fields}) in plain words; anything else keeps the server's message. */
const MESSAGES = (): Record<string, string> => ({
  invalid_leader: t`Choose another active member of this team.`,
  leader_cannot_be_removed: t`The leader cannot be removed. Hand the team over first, or leave it.`,
  leader_required: t`Only the team leader can do this.`,
  team_name_taken: t`Another team already uses this name.`,
  capacity_full: t`That team is already at its maximum size.`,
  team_locked: t`The roster is locked, so members cannot change now.`,
  active_submission: t`This team has a project submission, so it cannot be changed this way.`,
  team_max_below_largest_team: t`A team is already larger than this maximum.`,
  undo_expired: t`The five-minute undo window has passed.`,
  already_in_team: t`Someone from this team has joined another team since, so it cannot be restored.`,
  invalid_move: t`Choose a different team.`,
  not_disqualified: t`This project is not disqualified, so there is nothing to reinstate.`,
  fee_refunded: t`The entry fee was already refunded, so this project cannot be reinstated.`,
  plan_changed: t`The assignment plan changed since the preview. Preview it again.`,
  not_published: t`These results are not published.`,
  results_in_use: t`Prizes were already claimed or paid for these results, so they stay published.`,
  claim_not_verified: t`Verify the winner's payee details before recording the payout.`,
  same_person_verified: t`A second finance person must record a payout you verified.`,
  recovery_open: t`Close the open recovery for this payout before reversing it.`,
  prize_locked: t`A payout exists for this prize, so its amount and kind are fixed.`,
  payout_exists: t`This prize already has a recorded payout. Reverse it first.`,
  already_settled: t`This prize is already settled.`,
  claim_window_closed: t`The claim window for this prize has closed.`,
  claim_window_open: t`A prize is forfeited only after its claim window closes.`,
  share_not_confirmed: t`The winner must confirm their share first.`,
  recent_reauth_required: t`Confirm it's you, then try again.`,
  stale_version: t`This changed since you opened it. Refresh and try again.`,
});

export function commandErrorText(error: unknown): string {
  if (!error) return '';
  if (error instanceof StructuredApiError && error.code && MESSAGES()[error.code]) return MESSAGES()[error.code];
  return error instanceof Error ? error.message : t`Something went wrong. Please try again.`;
}

export const errorCode = (error: unknown) => error instanceof StructuredApiError ? error.code : undefined;
