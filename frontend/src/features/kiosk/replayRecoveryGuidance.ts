import { t } from "@lingui/core/macro";

// Safe human guidance for every 9c failure, including refusals before a row exists.
export const REPLAY_GUIDANCE: Record<string, string> = {
  rate_limited: t`Wait before retrying the same queued command.`,
  invalid_command: t`Load current work and capture a new handover with valid inputs.`,
  idempotency_conflict: t`Keep the original attempt. Capture a new command with a new identity.`,
  command_expired: t`Start a current operator shift, load the handover again and capture new evidence.`,
  clock_skew: t`Correct this browser's clock, then load current work and capture a new command.`,
  lease_expired: t`Start a new authenticated operator shift.`,
  station_revoked: t`Ask the space manager for the current enabled Station URL and PIN.`,
  session_mismatch: t`Unlock the current Station and start a new operator shift.`,
  feature_disabled: t`Ask the space manager to review the required handover feature before correcting online.`,
  module_disabled: t`Ask a Space Manager to turn this area back on before correcting online.`,
  permission_revoked: t`An operator with current permission must review and correct this handover.`,
  predecessor_missing: t`Inspect the preceding handover and load the current subject before starting a new command.`,
  predecessor_pending: t`Wait for the preceding command to finish, then retry the same queue.`,
  predecessor_failed: t`Review the preceding failure first. Correct each physical handover separately.`,
  evidence_missing: t`Check the upload connection. A correction requires a new uploaded photo.`,
  evidence_invalid: t`Take a new photo for a fresh correction; preserve the failed evidence.`,
  claim_in_progress: t`Wait for the other executor, then retry the same command.`,
  unsupported_operation_version: t`Refresh the application online and capture a new supported command.`,
  qr_revoked: t`Use the current active QR. Ask a manager to replace a revoked QR if needed.`,
  qr_mismatch: t`Verify the tool or box belongs to this handover and scan its current QR.`,
  request_state_changed: t`Review the current request. If another operator completed it, verify no change occurred here.`,
  loan_state_changed: t`Review the current loan. If already returned, verify no change occurred here.`,
  deposit_unsettled: t`Have authorized staff settle the blocking deposit before a new issue.`,
  presence_expired: t`Have the borrower establish current presence before correcting online.`,
  membership_required: t`Have authorized staff review the borrower's membership before correcting online.`,
  waiver_required: t`Have the borrower accept the current waiver before correcting online.`,
  box_scan_required: t`Assign and scan the current box before capturing a new issue.`,
  box_mismatch: t`Verify the assigned box is available and belongs to this handover.`,
  inventory_unavailable: t`Review current inventory availability before a new handover.`,
  storage_unavailable: t`Reconnect to evidence storage and retry the same queued command.`,
  server_unavailable: t`Reconnect to the server and retry the same queued command.`,
  target_missing: t`Load a handover that still exists in this makerspace.`,
  domain_invalid: t`Review the current handover details and capture a valid correction online.`,
};

export function replayGuidance(code: string | null) {
  return REPLAY_GUIDANCE[code ?? ""] ?? t`Keep this evidence and ask authorized staff to review the handover.`;
}

/** Translated name of an offline handover operation (`ReplayEnvelope.kind`). */
export function kioskOperationLabel(kind: string): string {
  switch (kind) {
    case "assign_box": return t`Assign box`;
    case "reviewed_issue": return t`Issue request`;
    case "reviewed_return": return t`Return request`;
    case "direct_handout": return t`Direct handout`;
    case "direct_return": return t`Direct return`;
    default: return kind.replace(/_/g, " ");
  }
}

/** Translated wording for how a retained failure was resolved. */
export function replayResolutionLabel(code: string): string {
  return code === "acknowledged_no_change" ? t`Acknowledged, no change`
    : code === "replaced_online" ? t`Replaced online` : code.replace(/_/g, " ");
}

/** Translated wording for a locally queued command's status. */
export function kioskCommandStatusLabel(status: string): string {
  switch (status) {
    case "queued": return t`Queued`;
    case "preparing": return t`Preparing`;
    case "uploading": return t`Uploading`;
    case "executing": return t`Sending`;
    case "succeeded": return t`Confirmed`;
    case "failed": return t`Failed`;
    default: return status.replace(/_/g, " ");
  }
}
