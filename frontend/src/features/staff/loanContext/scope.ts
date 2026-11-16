import { useSyncExternalStore } from "react";
import { currentSessionContext, onSessionCleared } from "../../../lib/api/sessionContext";
import { getSessionGeneration } from "../../../lib/api/sessionTokens";

/** Identity boundary only: the API remains the authority for every resource. */
export function useSessionScope() {
  const context = currentSessionContext();
  const generation = useSyncExternalStore(
    (notify) => onSessionCleared(changed => { if (changed === context) notify(); }),
    () => getSessionGeneration(context), () => 0,
  );
  return { context, generation };
}
