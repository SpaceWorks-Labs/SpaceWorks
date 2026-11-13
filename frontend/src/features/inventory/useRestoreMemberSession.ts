import { useEffect, useState, useSyncExternalStore } from "react";

import { hasSessionIdentity, refreshAccessToken } from "../../lib/api/sessionTokens";
import { browserIdentity, subscribeBrowserIdentity } from "../../lib/telemetry/sessionFence";

/**
 * A public page is a fresh document after "Sign in to borrow" returns here (`window.location.replace`),
 * so the in-memory access token is gone while the refresh cookie is still valid. The server's
 * browser-state answer says whether that cookie exists; only then is one refresh attempted, so an
 * anonymous visitor never makes a failing /auth/refresh call. The state bump re-renders the panel so
 * `useIntakeScope` reads the restored owner.
 */
export function useRestoreMemberSession(enabled: boolean) {
  const identity = useSyncExternalStore(subscribeBrowserIdentity, browserIdentity, () => "unknown" as const);
  const [, setRestored] = useState(0);
  useEffect(() => {
    if (!enabled || identity !== "auth_present" || hasSessionIdentity("person")) return;
    let active = true;
    void refreshAccessToken("person").then(ok => { if (active && ok) setRestored(count => count + 1); }).catch(() => undefined);
    return () => { active = false; };
  }, [enabled, identity]);
}
