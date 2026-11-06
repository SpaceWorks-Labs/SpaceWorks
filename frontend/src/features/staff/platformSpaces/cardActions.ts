import type { Action } from "../../../components/ui";
import type { HealthCard } from "./spacesApi";
import type { SimpleAction } from "./SimpleSpaceDialog";

export type DialogKind = SimpleAction | "transfer" | "schedule" | "purge" | "plan" | "keys" | "capabilities";

/**
 * Which lifecycle controls a card offers. The server refuses anything out of place (409); this only
 * hides the controls that cannot apply, so the menu never offers "Unblock" on an active space.
 */
export function cardActions(card: HealthCard, managedPlans: boolean, open: (kind: DialogKind) => void): Action[] {
  const archived = card.archived_at !== null;
  const busy = card.lifecycle_state === "importing" || card.lifecycle_state === "aborted";
  const suspended = card.suspended !== null || card.lifecycle_state === "suspended";
  const item = (label: string, kind: DialogKind, tone?: "danger"): Action => ({ label, onClick: () => open(kind), tone, confirms: true });
  const actions: Action[] = [];
  // Keys and capability data stay reachable in every state: rotating after a leak or purging a switched-off
  // capability must not wait for the space to be active (#190 follow-up).
  actions.push({ label: "Keys", onClick: () => open("keys") }, { label: "Capability data", onClick: () => open("capabilities") });
  if (archived) {
    actions.push(item("Unarchive", "unarchive"));
    actions.push(card.schedule ? item("Cancel schedule", "schedule/cancel") : item("Schedule purge", "schedule", "danger"));
    actions.push(item("Purge", "purge", "danger"));
    return actions;
  }
  if (!busy) {
    actions.push(suspended ? item("Unblock", "unsuspend") : item("Suspend", "suspend", "danger"));
    if (!suspended) actions.push(card.read_only ? item("Lift read-only", "read-only/lift") : item("Make read-only", "read-only"));
    actions.push(item("Transfer ownership", "transfer"));
    if (managedPlans) actions.push(item("Plan", "plan"));
    actions.push(card.schedule ? item("Cancel schedule", "schedule/cancel") : item("Schedule archive & purge", "schedule", "danger"));
    actions.push(item("Archive now", "archive", "danger"));
  }
  return actions;
}
