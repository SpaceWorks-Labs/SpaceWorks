import { useContext } from "react";
import { onSessionCleared } from "../../../lib/api/sessionContext";
import { getSessionOwner } from "../../../lib/api/sessionTokens";
import { PendingIntake } from "../../inventory/contextualIntake";
import { useIntakeScope } from "../../inventory/useIntakeScope";
import { StaffListContext } from "../StaffListContext";
import type { LinkedUseBody } from "./linkedConsumableApi";

type Entry = { owner: PendingIntake<LinkedUseBody>; busy: boolean; ordinaryUnknown: boolean };
const entries = new Map<string, Entry>();
let subscribed = false;
function subscribe() {
  if (subscribed) return;
  subscribed = true;
  onSessionCleared(context => {
    const owner = getSessionOwner(context);
    for (const key of entries.keys()) {
      const [entryContext, entryOwner] = JSON.parse(key) as [string, string];
      if (entryContext === context && entryOwner !== owner) { entries.get(key)?.owner.clear(); entries.delete(key); }
    }
  });
}
/** Session-owned memory survives panel unmount without persisting private notes. */
export function useLinkedUseOwners(tenant: number) {
  subscribe();
  const actor = useContext(StaffListContext).actorId;
  const session = useIntakeScope();
  const scope = JSON.stringify([session.context, session.owner, actor ?? null, tenant]);
  const admitted = () => Boolean(actor && session.owner === String(actor) && getSessionOwner(session.context) === String(actor));
  function entry(product: number): Entry {
    const key = JSON.stringify([session.context, session.owner, actor ?? null, tenant, product]);
    let value = entries.get(key);
    if (!value) { value = { owner: new PendingIntake<LinkedUseBody>(), busy: false, ordinaryUnknown: false }; entries.set(key, value); }
    return value;
  }
  return { scope, admitted, owner: (product: number) => entry(product).owner,
    acquire(product: number) { const value = entry(product); if (!admitted() || value.busy || value.ordinaryUnknown) return undefined; value.busy = true; return () => { value.busy = false; }; },
    ordinaryUnknown: (product: number) => entry(product).ordinaryUnknown,
    beginOrdinary(product: number) { const value = entry(product); if (!admitted() || value.busy || value.ordinaryUnknown) return undefined;
      value.busy = true; value.ordinaryUnknown = true;
      return (definite: boolean) => { value.busy = false; if (definite) value.ordinaryUnknown = false; }; },
    resolveOrdinary(product: number, canViewAudit: boolean) { const value = entry(product);
      if (!admitted() || !canViewAudit || value.busy) return false;
      value.ordinaryUnknown = false; return true; } };
}
