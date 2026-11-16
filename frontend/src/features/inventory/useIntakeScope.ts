import { useSyncExternalStore } from "react";
import { currentSessionContext, onSessionCleared } from "../../lib/api/sessionContext";
import { getSessionOwner } from "../../lib/api/sessionTokens";

/** Cache privacy boundary only; the server still authorizes every request. */
export function useIntakeScope() {
  const context = currentSessionContext();
  const owner = useSyncExternalStore(
    notify => onSessionCleared(changed => { if (changed === context) notify(); }),
    () => getSessionOwner(context), () => "",
  );
  return { context, owner };
}
