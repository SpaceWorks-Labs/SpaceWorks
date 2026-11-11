import { t } from "@lingui/core/macro";

const humanize = (value: string) => value.replace(/_/g, " ");

/** Translated wording for a backup archive `status`. */
export function backupArchiveStatusLabel(status: string): string {
  switch (status) {
    case "pending": return t`Pending`;
    case "running": return t`Running`;
    case "promoting": return t`Finishing`;
    case "available": return t`Available`;
    case "failed": return t`Failed`;
    case "expired": return t`Expired`;
    default: return humanize(status);
  }
}

/** Translated wording for a one-space restore `stage`. */
export function spaceRestoreStageLabel(stage: string): string {
  switch (stage) {
    case "requested": return t`Requested`;
    case "staging": return t`Preparing preview`;
    case "preview_ready": return t`Preview ready`;
    case "applying": return t`Restoring`;
    case "completed": return t`Completed`;
    case "failed": return t`Failed`;
    case "aborted": return t`Cancelled`;
    default: return humanize(stage);
  }
}

/** Translated wording for a whole-platform restore `stage`. */
export function deploymentRestoreStageLabel(stage: string): string {
  switch (stage) {
    case "requested": return t`Requested`;
    case "claimed": return t`Claimed`;
    case "preflight": return t`Checking`;
    case "quiesced": return t`Paused for your decision`;
    case "db_restoring": return t`Restoring the database`;
    case "objects_restoring": return t`Restoring files`;
    case "validating": return t`Validating`;
    case "completed": return t`Completed`;
    case "restored_quarantined": return t`Restored, held for review`;
    case "rolling_back": return t`Rolling back`;
    case "failed": return t`Failed`;
    case "aborted": return t`Cancelled`;
    default: return humanize(stage);
  }
}
