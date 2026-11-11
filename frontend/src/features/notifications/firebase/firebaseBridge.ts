import { getAccessToken } from "../../../lib/api/sessionTokens";
import { suspendPushForRefresh, resumePushAfterRefresh } from "../../../lib/api/authFreeze";
import { registerOwnFirebaseWorker } from "./firebaseRegistration";
import { currentFirebaseFid, type FirebaseWeb } from "./firebaseFid";
import { memberRequest } from "../../../lib/api";

type WorkerReply = { ok?: boolean };
function ack(worker: ServiceWorker, data: unknown): Promise<void> {
  return new Promise((resolve, reject) => {
    const channel = new MessageChannel();
    const timer = window.setTimeout(() => { channel.port1.close(); reject(new Error("Worker acknowledgement timed out")); }, 5000); // i18n-ignore: worker/challenge protocol failure; FirebaseBridgePage swallows it and shows its own translated message.
    channel.port1.onmessage = event => { clearTimeout(timer); channel.port1.close(); if ((event.data as WorkerReply)?.ok) resolve(); else reject(new Error("Worker refused operation")); }; // i18n-ignore: worker/challenge protocol failure; FirebaseBridgePage swallows it and shows its own translated message.
    worker.postMessage(data, [channel.port2]);
  });
}
/** Only call from the dedicated top-level, authenticated /firebase-alerts/setup page. */
export async function beginFirebaseBridge(makerspaceId: number, config: FirebaseWeb, vapidKey: string, onWake: () => void) {
  if (location.pathname !== "/firebase-alerts/setup") throw new Error("Wrong bridge page"); // i18n-ignore: developer guard; FirebaseBridgePage swallows it and shows its own translated message.
  if (Notification.permission !== "granted") throw new Error("Notification permission is required"); // i18n-ignore: FirebaseBridgePage swallows it and shows its own translated message.
  const registration = await registerOwnFirebaseWorker();
  if (!navigator.serviceWorker.controller || navigator.serviceWorker.controller.scriptURL !== registration.active?.scriptURL) throw new Error("Bridge must be reloaded under its worker"); // i18n-ignore: developer guard; FirebaseBridgePage swallows it and shows its own translated message.
  const worker = navigator.serviceWorker.controller, previous = await suspendPushForRefresh();
  let listener: ((event: MessageEvent) => void) | undefined, epoch: string | null = null, active = true;
  try {
    const fid = await currentFirebaseFid(config, vapidKey, registration), challenge = crypto.randomUUID();
    let deliver!: (nonce: string) => void;
    const proof = new Promise<string>(resolve => { deliver = resolve; });
    listener = (event: MessageEvent) => {
      if (!active || event.source !== worker || !event.data || typeof event.data !== "object") return;
      if (event.data.kind === "spaceworks_fcm_challenge" && event.data.challenge === challenge && typeof event.data.nonce === "string") deliver(event.data.nonce);
      if (event.data.kind === "spaceworks_inbox_changed" && epoch && event.data.owner_epoch === epoch) onWake();
    };
    navigator.serviceWorker.addEventListener("message", listener);
    await ack(worker, { kind: "expect", challenge });
    const begun = await memberRequest<{ challenge: string }>(`/notifications/browser-firebase/${makerspaceId}/challenge`, { method: "POST", body: JSON.stringify({ project_id: config.projectId, fid, challenge_id: challenge }) });
    if (begun.challenge !== challenge) throw new Error("Challenge mismatch"); // i18n-ignore: worker/challenge protocol failure; FirebaseBridgePage swallows it and shows its own translated message.
    let timer = 0;
    const nonce = await Promise.race([proof, new Promise<never>((_, reject) => { timer = window.setTimeout(() => reject(new Error("Challenge timed out")), 30000); })]).finally(() => window.clearTimeout(timer)); // i18n-ignore: worker/challenge protocol failure; FirebaseBridgePage swallows it and shows its own translated message.
    const confirmed = await memberRequest<{ owner_epoch: string }>(`/notifications/browser-firebase/${makerspaceId}/confirm`, { method: "POST", body: JSON.stringify({ project_id: config.projectId, fid, challenge, nonce }) });
    await ack(worker, { kind: "activate", owner_epoch: confirmed.owner_epoch, space: makerspaceId, challenge }); epoch = confirmed.owner_epoch;
    const dispose = () => { active = false; epoch = null; if (listener) navigator.serviceWorker.removeEventListener("message", listener); };
    return { dispose, async freeze() { dispose(); await ack(worker, { kind: "freeze" }); } };
  } catch (error) {
    active = false; if (listener) navigator.serviceWorker.removeEventListener("message", listener);
    await resumePushAfterRefresh(previous, getAccessToken("person")); throw error;
  }
}
/** Revoke only this account's selected space; do not unregister the shared Firebase worker. */
export async function disableFirebaseForSpace(makerspaceId: number, config: FirebaseWeb, vapidKey: string) {
  const registration = await registerOwnFirebaseWorker();
  const fid = await currentFirebaseFid(config, vapidKey, registration);
  await memberRequest<void>(`/notifications/browser-firebase/${makerspaceId}/challenge`, { method: "DELETE", body: JSON.stringify({ project_id: config.projectId, fid }) });
}
