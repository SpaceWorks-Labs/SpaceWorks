import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../../../../lib/api/errors";
import type { BindingState, Capability, ControlCommand, TargetType } from "./adaptersApi";

/** Plain-language copy for the typed refusals of the adapter routes (ADAPTER-CONSOLE contract). */
export function adapterErrorMessage(error: unknown): string {
  if (!(error instanceof StructuredApiError)) return error instanceof Error ? error.message : t`Something went wrong. Try again.`;
  const limit = typeof error.body.limit === "number" || typeof error.body.limit === "string" ? String(error.body.limit) : "";
  switch (error.code) {
    case "adapter_bridges_quota_reached": return limit ? t`This space already has the ${limit} bridges its plan allows. Revoke one you no longer use, or ask the platform operator to raise the limit.`
      : t`This space has reached the number of bridges its plan allows. Revoke one you no longer use, or ask the platform operator to raise the limit.`;
    case "adapter_watch_streams_quota_reached": return t`Too many camera watches are open at once. End one, or wait for it to expire, then try again.`;
    case "adapter_snapshots_quota_reached": return t`This space has used all the camera snapshots its plan allows this month.`;
    case "binding_exists": return t`That target is already bound to this adapter.`;
    case "adapter_revoked": return t`This adapter has been revoked and can no longer be used.`;
    case "capability_missing": return t`This target does not offer that action.`;
    case "capability_not_declared": return t`The adapter has not said it can do that yet. Let it connect once, then try again.`;
    case "capability_target_mismatch": return t`That capability cannot work with this kind of target.`;
    case "command_unknown": return t`The adapter does not know that command.`;
    case "pose_not_calibrated": return t`No position is saved for that place yet. Calibrate it first.`;
    case "invalid_pose": return t`That position is not valid. Use numbers only.`;
    case "watch_ended": return t`That camera watch has already ended. Start a new one.`;
    case "credential_in_use": return t`That credential is already in use by someone else.`;
    case "invalid_pin": return t`A PIN is 6 to 12 digits.`;
    case "weak_pin": return t`That PIN is too easy to guess. Choose another.`;
    case "adapter_unavailable": return t`The adapter is offline right now, so the command was not sent.`;
    default: return error.message;
  }
}

export function stateLabel(state: BindingState | undefined): string {
  switch (state) {
    case "idle": return t`Idle`;
    case "preparing": return t`Preparing`;
    case "running": return t`Running`;
    case "paused": return t`Paused`;
    case "finished": return t`Finished`;
    case "failed": return t`Failed`;
    case "error": return t`Error`;
    case "offline": return t`Offline`;
    case "maintenance": return t`Maintenance`;
    default: return t`No report yet`;
  }
}
export const stateTone = (state: BindingState | undefined) =>
  state === "running" || state === "finished" ? "success" as const
    : state === "failed" || state === "error" ? "danger" as const
      : state === "paused" || state === "preparing" || state === "maintenance" || state === "offline" ? "warn" as const : "neutral" as const;

export function targetTypeLabel(type: TargetType | string): string {
  switch (type) {
    case "machine": return t`Machine`;
    case "machine_type": return t`Machine type`;
    case "storage_location": return t`Storage location`;
    case "item": return t`Item`;
    case "box": return t`Box`;
    case "door": return t`Door`;
    case "space": return t`Space`;
    default: return type;
  }
}

export function controlLabel(command: ControlCommand | string): string {
  switch (command) {
    case "pause": return t`Pause`;
    case "resume": return t`Resume`;
    case "cancel": return t`Cancel job`;
    case "power": return t`Power`;
    default: return command;
  }
}

export const capabilityLabel = (cap: Capability | string) => {
  const name = typeof cap === "string" ? cap : cap.name;
  return name.replace(/[._]/g, " ");
};
