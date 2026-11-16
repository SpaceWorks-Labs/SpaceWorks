import { useEffect, useRef, useState, type ReactNode } from "react";

import { getSessionOwner } from "../../../lib/api/sessionTokens";
import { onSessionCleared, type SessionContext } from "../../../lib/api/sessionContext";
import { useIntakeScope } from "../../inventory/useIntakeScope";

/** Pins a private-feed card to the session owner it was mounted for. */
export type FeedScope = { key: readonly [SessionContext, string]; admitted: () => boolean };

/**
 * A private calendar URL is a bearer credential: it must never outlive (or arrive after) the
 * account that asked for it. Any owner change remounts the subtree, and a response that lands
 * after the change is refused by `admitted()`. Cache privacy only; the API authorizes each call.
 */
export function OwnerScoped({ children }: { children: (scope: FeedScope) => ReactNode }) {
  const { context, owner } = useIntakeScope();
  const [revision, setRevision] = useState(0);
  useEffect(() => onSessionCleared(changed => {
    if (changed === context && getSessionOwner(context) !== owner) setRevision(value => value + 1);
  }), [context, owner]);
  if (!owner) return null;
  return <Pinned key={JSON.stringify([context, owner, revision])} context={context} owner={owner}>{children}</Pinned>;
}

function Pinned({ context, owner, children }: { context: SessionContext; owner: string; children: (scope: FeedScope) => ReactNode }) {
  const live = useRef(false);
  useEffect(() => {
    live.current = true;
    const unsubscribe = onSessionCleared(changed => {
      if (changed === context && getSessionOwner(context) !== owner) live.current = false;
    });
    return () => { live.current = false; unsubscribe(); };
  }, [context, owner]);
  return <>{children({ key: [context, owner], admitted: () => live.current && getSessionOwner(context) === owner })}</>;
}
