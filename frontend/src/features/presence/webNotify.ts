// A local web notification for the renew prompt. The server also emits the personal
// `presence.expired` envelope (inbox + native push); this only covers an open tab.
export type WebNotifyPermission = NotificationPermission | "unsupported";

export function webNotifyPermission(): WebNotifyPermission {
  return typeof Notification === "undefined" ? "unsupported" : Notification.permission;
}

/** Must run from a user gesture; browsers ignore unprompted permission requests. */
export async function requestWebNotify(): Promise<WebNotifyPermission> {
  if (typeof Notification === "undefined") return "unsupported";
  try {
    return await Notification.requestPermission();
  } catch {
    return Notification.permission;
  }
}

/** Prefer the service worker (works on Android/PWA installs); fall back to a page notification. */
export async function showWebNotification(title: string, body: string, tag: string): Promise<void> {
  if (webNotifyPermission() !== "granted") return;
  try {
    const registration = await navigator.serviceWorker?.getRegistration();
    if (registration) { await registration.showNotification(title, { body, tag }); return; }
    new Notification(title, { body, tag });
  } catch {
    // A failed local notification must never break the in-app prompt.
  }
}
