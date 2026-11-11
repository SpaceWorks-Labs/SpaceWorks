export function isOwnFirebaseRegistration(registration: ServiceWorkerRegistration): boolean {
  if (registration.scope !== new URL("/firebase-alerts/", location.origin).href) return false;
  const workers = [registration.active, registration.waiting, registration.installing].filter(Boolean);
  return workers.length > 0 && workers.every(worker => worker!.scriptURL === new URL("/firebase-alerts-sw.js", location.origin).href);
}
export async function registerOwnFirebaseWorker(): Promise<ServiceWorkerRegistration> {
  const existing = await navigator.serviceWorker.getRegistration("/firebase-alerts/");
  if (existing?.scope === new URL("/firebase-alerts/", location.origin).href && !isOwnFirebaseRegistration(existing)) throw new Error("Notification worker scope is already in use"); // i18n-ignore: worker identity guard; FirebaseBridgePage swallows it and shows its own translated message.
  const registration = await navigator.serviceWorker.register("/firebase-alerts-sw.js", { scope: "/firebase-alerts/", updateViaCache: "none" });
  if (!isOwnFirebaseRegistration(registration)) throw new Error("Notification worker identity mismatch"); // i18n-ignore: worker identity guard; FirebaseBridgePage swallows it and shows its own translated message.
  return registration;
}
