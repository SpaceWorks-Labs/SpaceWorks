import { useEffect, useRef } from "react";
import { onSessionCleared } from "../../lib/api/sessionContext";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { PendingIntake, type SelfBody } from "./contextualIntake";
import { useIntakeScope } from "./useIntakeScope";

/** Keep a mobile-sheet intent in its parent while retiring old identities and tenants. */
export function usePendingIntakeOwner(scope: string) {
  const session = useIntakeScope();
  const current = useRef({ scope, owner: new PendingIntake<SelfBody>() });
  if (current.current.scope !== scope) current.current = { scope, owner: new PendingIntake<SelfBody>() };
  const entry = current.current;
  useEffect(() => {
    const unsubscribe = onSessionCleared(context => {
      if (context === session.context && getSessionOwner(context) !== session.owner) entry.owner.retire(entry.scope);
    });
    return () => { unsubscribe(); entry.owner.retire(entry.scope); };
  }, [entry, session.context, session.owner]);
  return entry.owner;
}
