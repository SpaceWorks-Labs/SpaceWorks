import { registerOwnFirebaseWorker } from "./firebaseRegistration";
import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { memberRequest } from "../../../lib/api";
import { beginFirebaseBridge, disableFirebaseForSpace } from "./firebaseBridge";

type PublicConfig = { api_key: string; auth_domain: string; project_id: string; app_id: string; messaging_sender_id: string; vapid_public_key: string };
/** Top-level page controlled only by /firebase-alerts/ worker; no nonce or FID enters the URL. */
export function FirebaseBridgePage() {
  const queryClient = useQueryClient();
  const bridge = useRef<{ dispose(): void } | null>(null);
  const generation = useRef(0);
  useEffect(() => () => { generation.current++; bridge.current?.dispose(); bridge.current = null; }, []);
  const raw = new URLSearchParams(location.search).get("space") ?? "";
  const id = /^[1-9][0-9]{0,9}$/.test(raw) ? Number(raw) : 0;
  const config = useQuery({ queryKey: ["firebase-browser-config", id], queryFn: () => memberRequest<{ configured: boolean; config: PublicConfig | null }>(`/notifications/browser-firebase/${id}/config`), enabled: Boolean(id), retry: false });
  const [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  async function enable() {
    const value = config.data?.config; if (!value || !id) return;
    setBusy(true); setMessage(""); const current = ++generation.current;
    try {
      if (await Notification.requestPermission() !== "granted") throw new Error("permission");
      const registration = await registerOwnFirebaseWorker();
      if (!navigator.serviceWorker.controller || navigator.serviceWorker.controller.scriptURL !== registration.active?.scriptURL) { location.reload(); return; }
      bridge.current?.dispose();
      const opened = await beginFirebaseBridge(id, { apiKey: value.api_key, authDomain: value.auth_domain, projectId: value.project_id, appId: value.app_id, messagingSenderId: value.messaging_sender_id }, value.vapid_public_key, () => { void queryClient.invalidateQueries({ queryKey: ["notifications-inbox", id] }); void queryClient.invalidateQueries({ queryKey: ["notifications-unread", id] }); });
      if (generation.current !== current) { opened.dispose(); return; }
      bridge.current = opened;
      setMessage(t`Browser notifications are ready. You can return to your account.`);
    } catch { if (generation.current === current) setMessage(t`Browser notifications could not be enabled. Check your permission and try again.`); }
    finally { if (generation.current === current) setBusy(false); }
  }
  async function disable() {
    const value = config.data?.config; if (!value || !id) return;
    setBusy(true); setMessage("");
    try {
      await disableFirebaseForSpace(id, { apiKey: value.api_key, authDomain: value.auth_domain, projectId: value.project_id, appId: value.app_id, messagingSenderId: value.messaging_sender_id }, value.vapid_public_key);
      bridge.current?.dispose(); bridge.current = null;
      setMessage(t`Browser notifications are off for this space.`);
    } catch { setMessage(t`Browser notifications could not be disabled. Try again.`); }
    finally { setBusy(false); }
  }
  if (!id) return <p role="alert">{t`Choose a makerspace before enabling notifications.`}</p>;
  if (config.isPending) return <p role="status">{t`Loading notification settings…`}</p>;
  if (config.error || !config.data?.configured) return <p role="alert">{t`Browser notifications are unavailable for this space.`}</p>;
  return <main className="desk-panel grid gap-3 p-5"><h1>{t`Browser notifications`}</h1>
    <p>{t`Allow notifications to receive a generic notice when your inbox changes.`}</p>
    <button type="button" disabled={busy} onClick={() => void enable()}>{busy ? t`Working…` : t`Enable notifications`}</button>
    <button type="button" disabled={busy} onClick={() => void disable()}>{t`Disable notifications for this space`}</button>
    {message ? <p role="status">{message}</p> : null}<a href="/member">{t`Return to your account`}</a>
  </main>;
}





