import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { currentTheme } from "../../lib/theme";
import { loadTurnstile } from "./turnstileScript";

/**
 * The Cloudflare Turnstile check, shown only after a sign-in answers `captcha_required`
 * (#62: off until the deployment has keys). It loads Cloudflare's script the first time it
 * mounts; nothing is fetched while it is not on screen. The token goes back to the caller,
 * which resubmits with the `X-Turnstile-Token` header.
 */
export function TurnstileWidget({ siteKey, action, onToken, onExpired }: {
  siteKey: string;
  action: string;
  onToken: (token: string) => void;
  onExpired?: () => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const handlers = useRef({ onToken, onExpired });
  handlers.current = { onToken, onExpired };
  useEffect(() => {
    let widgetId: string | undefined;
    let active = true;
    void loadTurnstile().then(api => {
      if (!active || !container.current) return;
      widgetId = api.render(container.current, {
        sitekey: siteKey, action, theme: currentTheme(),
        callback: token => handlers.current.onToken(token),
        "expired-callback": () => handlers.current.onExpired?.(),
        "error-callback": () => setStatus("failed"),
      });
      setStatus("ready");
    }).catch(() => { if (active) setStatus("failed"); });
    return () => {
      active = false;
      if (widgetId !== undefined) window.turnstile?.remove(widgetId);
    };
  }, [siteKey, action]);
  return <div className="grid gap-2" role="group" aria-label={t`Confirm you're a person`}>
    <p className="text-sm font-semibold text-ink">{t`Confirm you're a person`}</p>
    <div ref={container} className="min-h-16" />
    <p aria-live="polite" className="text-sm text-muted">
      {status === "loading" ? t`Loading the check…` : status === "failed"
        ? t`The check couldn't load. Check your connection, then try again.` : ""}
    </p>
  </div>;
}
