import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { BellRing } from "lucide-react";
import { staffRequest } from "../../lib/api";

type Key = { configured: boolean; public_key: string };
const SCOPE = "/browser-alerts/";

function keyBytes(base64url: string) {
  const padded = (base64url + "===".slice((base64url.length + 3) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(padded), char => char.charCodeAt(0));
}

/** X38: opt this browser in or out of notifications for this space (needs the deployment's VAPID key). */
export function BrowserAlertsToggle({ makerspaceId }: { makerspaceId: number }) {
  const [key, setKey] = useState<Key | null>(null);
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const supported = typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  const path = `/notifications/browser-alerts/${makerspaceId}`;
  useEffect(() => {
    if (!supported) return;
    let live = true;
    // Ask for the per-space state only when the deployment has a push key: without one the
    // state endpoint can only answer 404, which would surface as a console error on every visit.
    void staffRequest<Key>("/notifications/browser-alerts/key")
      .then(async (value) => {
        if (!value.configured) { if (live) setKey(value); return; }
        await staffRequest<{ subscribed_browsers: number }>(path);
        const registration = await navigator.serviceWorker.getRegistration(SCOPE);
        const existing = await registration?.pushManager.getSubscription();
        if (live) { setKey(value); setSubscribed(Boolean(existing)); }
      }).catch(() => { if (live) setKey(null); });
    return () => { live = false; };
  }, [path, supported]);
  // Hidden while unsupported, while the deployment has no key, or while notifications.web_push is off (404).
  if (!supported || !key?.configured || subscribed === null) return null;
  const toggle = async () => {
    setBusy(true); setMessage("");
    try {
      const registration = await navigator.serviceWorker.register("/browser-alerts-sw.js", { scope: SCOPE, updateViaCache: "none" });
      const existing = await registration.pushManager.getSubscription();
      if (subscribed && existing) {
        await staffRequest(path, { method: "DELETE", body: JSON.stringify({ endpoint: existing.endpoint }) });
        await existing.unsubscribe();
        setSubscribed(false); setMessage(t`Browser notifications are off for this space.`);
      } else {
        if (await Notification.requestPermission() !== "granted") { setMessage(t`Your browser blocked notifications. Allow them in its site settings to turn this on.`); return; }
        const subscription = existing ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key.public_key) });
        await staffRequest(path, { method: "POST", body: JSON.stringify(subscription.toJSON()) });
        setSubscribed(true); setMessage(t`This browser will show new messages from your inbox.`);
      }
    } catch {
      setMessage(t`Couldn't change browser notifications. Try again.`);
    } finally { setBusy(false); }
  };
  return <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-panel p-3 text-sm">
    <BellRing aria-hidden="true" className="size-4 text-brand" />
    <span className="grow">{t`Browser notifications: `}{subscribed ? t`on in this browser` : "off"}</span>
    <button type="button" className="desk-button" disabled={busy} onClick={() => void toggle()}>{busy ? t`Working…` : subscribed ? t`Turn off` : t`Turn on`}</button>
    {message ? <p role="status" className="basis-full text-muted">{message}</p> : null}
  </div>;
}
