import type { MachineServiceRequest } from "../../../../generated/api";
import { blankServiceDraft, type ServiceActionName, type ServiceDraft } from "./serviceDrafts";

/** The consumable still held by a RUNNING job, in the hold's own unit; 0 when nothing is held. */
export function runningHold(request: MachineServiceRequest): number {
  if (request.status !== "in_progress") return 0;
  const held = Number(request.reserved_quantity ?? request.reserved_grams ?? 0);
  return Number.isFinite(held) && held > 0 ? held : 0;
}

/** Decision 61a: elapsed ÷ estimated duration × planned quantity, capped at the hold. */
export function estimateConsumed(request: MachineServiceRequest, now = Date.now()): string {
  const hold = runningHold(request);
  const minutes = request.estimated_minutes;
  const planned = Number(request.planned_quantity ?? request.planned_grams ?? 0);
  if (!hold || !request.started_at || !minutes || !(planned > 0)) return "";
  const elapsed = Math.max(0, (now - new Date(request.started_at).getTime()) / 60000);
  return Math.min(hold, (elapsed / minutes) * planned).toFixed(2);
}

/** Open an action form with fresh values; a running cancel is pre-filled with the estimate. */
export function openAction(draft: ServiceDraft, request: MachineServiceRequest, name: ServiceActionName): ServiceDraft {
  const actionValues = blankServiceDraft().actionValues;
  if (name === "cancel" && runningHold(request)) {
    actionValues.cancel_hold = String(runningHold(request));
    actionValues.consumed_quantity = estimateConsumed(request) || "0";
  }
  return { ...draft, action: { id: request.id, name }, actionValues: name === "cancel" ? actionValues : draft.actionValues };
}

/** Cancel body: a positive confirmed amount only when the job holds material. */
export function cancelBody(values: ServiceDraft["actionValues"]) {
  const body: { reason?: string; consumed_quantity?: string } = values.reason ? { reason: values.reason } : {};
  if (values.cancel_hold && Number(values.consumed_quantity) > 0) body.consumed_quantity = values.consumed_quantity;
  return body;
}
