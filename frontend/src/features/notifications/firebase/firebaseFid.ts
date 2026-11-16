export type FirebaseWeb = { apiKey: string; authDomain: string; projectId: string; appId: string; messagingSenderId: string };
/** The SDK supplies the FID; it is never exposed in UI, URL, logs or browser persistence by this app. */
export async function currentFirebaseFid(config: FirebaseWeb, vapidKey: string, registration: ServiceWorkerRegistration): Promise<string> {
  const [appSdk, messagingSdk] = await Promise.all([import("firebase/app"), import("firebase/messaging")]);
  if (!(await messagingSdk.isSupported())) throw new Error("Browser messaging unsupported"); // i18n-ignore: SDK failure; FirebaseBridgePage swallows it and shows its own translated message.
  const existing = appSdk.getApps().find(item => item.name === "spaceworks-push");
  if (existing && existing.options.projectId !== config.projectId) throw new Error("Firebase project changed; reload required"); // i18n-ignore: SDK failure; FirebaseBridgePage swallows it and shows its own translated message.
  const app = existing ?? appSdk.initializeApp(config, "spaceworks-push"), messaging = messagingSdk.getMessaging(app);
  let unsubscribe: () => void = () => undefined, timer = 0;
  const fid = new Promise<string>((resolve, reject) => {
    timer = window.setTimeout(() => reject(new Error("Registration timed out")), 15000); // i18n-ignore: SDK failure; FirebaseBridgePage swallows it and shows its own translated message.
    unsubscribe = messagingSdk.onRegistered(messaging, resolve);
  });
  try { const [, value] = await Promise.all([messagingSdk.register(messaging, { vapidKey, serviceWorkerRegistration: registration }), fid]); return value; }
  finally { window.clearTimeout(timer); unsubscribe(); }
}
