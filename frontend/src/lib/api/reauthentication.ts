/** One session-bound step-up prompt shared by concurrent protected mutations. */
import { currentSessionContext, type SessionContext } from "./sessionContext";
const handlers = new Map<SessionContext, () => Promise<boolean>>();
const pending = new Map<SessionContext, Promise<boolean>>();

export function setReauthenticationHandler(next: () => Promise<boolean>, context = currentSessionContext()) {
  handlers.set(context, next);
  return () => { if (handlers.get(context) === next) handlers.delete(context); };
}

export function requestReauthentication(context = currentSessionContext()): Promise<boolean> {
  const handler = handlers.get(context);
  if (!handler) return Promise.resolve(false);
  if (!pending.has(context)) pending.set(context, handler().finally(() => { pending.delete(context); }));
  return pending.get(context)!;
}

export function browserSessionIdentity(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as Record<string, unknown>;
    return payload.sid ? `${String(payload.user_id)}:${String(payload.sid)}:${String(payload.surface)}` : "";
  } catch { return ""; }
}
