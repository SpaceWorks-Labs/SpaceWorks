/** One session-bound step-up prompt shared by concurrent protected mutations. */
let handler: (() => Promise<boolean>) | undefined;
let pending: Promise<boolean> | undefined;

export function setReauthenticationHandler(next: () => Promise<boolean>) {
  handler = next;
  return () => { if (handler === next) handler = undefined; };
}

export function requestReauthentication(): Promise<boolean> {
  if (!handler) return Promise.resolve(false);
  if (!pending) pending = handler().finally(() => { pending = undefined; });
  return pending;
}

export function browserSessionIdentity(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as Record<string, unknown>;
    return payload.sid ? `${String(payload.user_id)}:${String(payload.sid)}:${String(payload.surface)}` : "";
  } catch { return ""; }
}
