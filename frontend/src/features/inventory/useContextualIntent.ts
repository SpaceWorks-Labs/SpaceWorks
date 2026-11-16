import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { PendingIntake, submitContextualSelf, type RequestFields, type SelfBody, type SelfResult } from "./contextualIntake";

/** The caller remounts on actor/session/tenant changes; the frozen intent is never persisted. */
export function useContextualIntent(scope: string, slug: string, owner: PendingIntake<SelfBody>, onConceal: () => void, onValidation: () => void, admitted: () => boolean, onSuccess?: (result: SelfResult, scope: string) => void) {
  const pending = useRef(owner);
  const state = useSyncExternalStore(listener => owner.subscribe(listener), () => owner.state(scope), () => "idle" as const);
  const [error, setError] = useState<string>();
  const scopeRef = useRef(scope);
  const live = useRef(true);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  useEffect(() => { owner.retainOnly(scope); }, [owner, scope]);
  pending.current = owner;
  scopeRef.current = scope;
  async function send(body: Readonly<SelfBody>): Promise<SelfResult | undefined> {
    if (!admitted()) { onConceal(); return undefined; }
    const started = scopeRef.current; const operationOwner = pending.current;
    const wasUncertain = operationOwner.wasUncertain(started);
    if (!operationOwner.acquire(started, body)) return undefined;
    setError(undefined);
    try {
      const result = await submitContextualSelf(slug, body);
      if (!admitted() || !operationOwner.complete(started, body)) { operationOwner.release(started, body); return undefined; }
      if (operationOwner.has(started) || !admitted()) return undefined;
      onSuccess?.(result, started);
      if (!live.current || scopeRef.current !== started) return undefined;
      return result;
    } catch (caught) {
      const failure = caught as { status?: number };
      if (failure?.status === 400 && !wasUncertain) {
        const cleared = operationOwner.complete(started, body);
        if (!cleared || !live.current || scopeRef.current !== started) return undefined;
        setError(t`Request not accepted.`);
        onValidation();
        return undefined;
      }
      operationOwner.release(started, body);
      if (!live.current || scopeRef.current !== started) return undefined;
      if ([401, 403, 404].includes(failure?.status ?? 0)) onConceal();
      setError(caught instanceof Error ? caught.message : t`Request outcome is unknown. Review your request history before trying again.`);
      return undefined;
    }
  }
  function begin(fields: RequestFields, eventRegistrationId: number | null, bookingToken: string | null) {
    if (!admitted()) { onConceal(); return Promise.resolve(undefined); }
    const body = pending.current.begin(scope, { ...fields, operation_id: crypto.randomUUID(), event_registration_id: eventRegistrationId, booking_token: bookingToken });
    return send(body);
  }
  function retry() { const body = pending.current.current(scope); return body ? send(body) : Promise.resolve(undefined); }
  return { state, error, begin, retry, pendingBody: pending.current.current(scope) };
}
