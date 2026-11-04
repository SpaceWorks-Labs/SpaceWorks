import { lazy, Suspense, useState } from "react";
import { captchaChallenge } from "../../lib/api/authErrorCopy";

const TurnstileWidget = lazy(() => import("./TurnstileWidget").then(m => ({ default: m.TurnstileWidget })));

export const TURNSTILE_TOKEN_HEADER = "X-Turnstile-Token";

/**
 * The CAPTCHA step of a sign-in form. `configuredKey` is `/api/v1/config`'s `turnstile_site_key`
 * (absent until the deployment has keys); without it the widget's code is never even imported.
 * `catchError` returns true when the refusal asked for a check, and `slot` then renders it;
 * the token arrives in `onToken`, which resubmits with `tokenHeaders(token)`.
 */
export function useTurnstileGate(configuredKey: string | undefined, onToken: (token: string) => void) {
  const [challenge, setChallenge] = useState<{ siteKey: string; action: string; round: number } | null>(null);
  const catchError = (error: unknown) => {
    const next = captchaChallenge(error);
    if (!next || !configuredKey) return false;
    setChallenge(current => ({ siteKey: next.siteKey || configuredKey, action: next.action, round: (current?.round ?? 0) + 1 }));
    return true;
  };
  const slot = challenge ? <Suspense fallback={<p role="status" className="text-sm text-muted">Loading the check…</p>}>
    <TurnstileWidget key={challenge.round} siteKey={challenge.siteKey} action={challenge.action}
      onToken={onToken} onExpired={() => setChallenge(current => current && { ...current, round: current.round + 1 })} />
  </Suspense> : null;
  return { catchError, slot, reset: () => setChallenge(null) };
}

export function tokenHeaders(token?: string): Record<string, string> {
  return token ? { [TURNSTILE_TOKEN_HEADER]: token } : {};
}
