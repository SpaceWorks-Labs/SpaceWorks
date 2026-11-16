import { waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { freezeBeforeAuthMutation, queuePrivacyFreeze, resumePushAfterRefresh } from "./authFreeze";

it("does not touch service workers for a normal read", async () => {
  const getRegistration = vi.fn();
  vi.stubGlobal("navigator", { serviceWorker: { getRegistration } });
  try { await freezeBeforeAuthMutation("/auth/me", "GET"); expect(getRegistration).not.toHaveBeenCalled(); }
  finally { vi.unstubAllGlobals(); }
});
it("retires an inactive Firebase worker without blocking sign-in", async () => {
  vi.stubGlobal("navigator", { serviceWorker: { getRegistration: vi.fn().mockResolvedValue({ scope: `${location.origin}/firebase-alerts/`, active: null, waiting: { scriptURL: `${location.origin}/firebase-alerts-sw.js` }, unregister: vi.fn().mockResolvedValue(true), pushManager: { getSubscription: vi.fn().mockResolvedValue(null) } }) } });
  try { await expect(freezeBeforeAuthMutation("/auth/login", "POST")).resolves.toBeUndefined(); }
  finally { vi.unstubAllGlobals(); }
});
it("waits for worker freeze acknowledgement before resolving an auth mutation fence", async () => {
  let port: MessagePort | undefined;
  const postMessage = vi.fn((_data: unknown, ports: MessagePort[]) => { port = ports[0]; });
  vi.stubGlobal("navigator", { serviceWorker: { getRegistration: vi.fn().mockResolvedValue({ scope: `${location.origin}/firebase-alerts/`, active: { scriptURL: `${location.origin}/firebase-alerts-sw.js`, postMessage } }) } });
  try {
    let done = false;
    const pending = freezeBeforeAuthMutation("/auth/login", "POST").then(() => { done = true; });
    await waitFor(() => expect(postMessage).toHaveBeenCalledWith({ kind: "freeze" }, expect.any(Array)));
    expect(done).toBe(false);
    port!.postMessage({ ok: true }); await pending; expect(done).toBe(true);
  } finally { vi.unstubAllGlobals(); }
});

it("an identity clear queues a freeze that the next login must await", async () => {
  const ports: MessagePort[] = [];
  const worker = { scriptURL: `${location.origin}/firebase-alerts-sw.js`, postMessage: (_data: unknown, transferred: MessagePort[]) => { ports.push(transferred[0]); } };
  vi.stubGlobal("navigator", { serviceWorker: { getRegistration: vi.fn().mockResolvedValue({ scope: `${location.origin}/firebase-alerts/`, active: worker }) } });
  try {
    queuePrivacyFreeze(); let complete = false;
    const login = freezeBeforeAuthMutation("/auth/login", "POST").then(() => { complete = true; });
    await waitFor(() => expect(ports).toHaveLength(1)); expect(complete).toBe(false);
    ports[0].postMessage({ ok: true });
    await waitFor(() => expect(ports).toHaveLength(2)); expect(complete).toBe(false);
    ports[1].postMessage({ ok: true }); await login; expect(complete).toBe(true);
  } finally { vi.unstubAllGlobals(); }
});



it("does not message, unsubscribe, or unregister an ancestor root worker", async () => {
  const postMessage = vi.fn(), unregister = vi.fn(), unsubscribe = vi.fn();
  vi.stubGlobal("navigator", { serviceWorker: { getRegistration: vi.fn().mockResolvedValue({ scope: `${location.origin}/`, active: { scriptURL: `${location.origin}/sw.js`, postMessage }, unregister, pushManager: { getSubscription: async () => ({ unsubscribe }) } }) } });
  try { await freezeBeforeAuthMutation("/auth/login", "POST"); expect(postMessage).not.toHaveBeenCalled(); expect(unregister).not.toHaveBeenCalled(); expect(unsubscribe).not.toHaveBeenCalled(); }
  finally { vi.unstubAllGlobals(); }
});


it("does not restore an old owner ticket when the fresh actor check denies it", async () => {
  const postMessage = vi.fn(); vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ may_resume: false }), { status: 200 })));
  try { await resumePushAfterRefresh({ worker: { postMessage } as unknown as ServiceWorker, ticket: "old-ticket", ownerEpoch: "old-epoch" }, "new-actor-access"); expect(postMessage).not.toHaveBeenCalled(); }
  finally { vi.unstubAllGlobals(); }
});


it.each(["/auth/reauth", "/auth/reauth/passkey/options", "/auth/reauth/passkey/verify"])("step-up %s leaves notification registration untouched", async path => {
  const getRegistration = vi.fn(); vi.stubGlobal("navigator", { serviceWorker: { getRegistration } });
  try { await freezeBeforeAuthMutation(path, "POST"); expect(getRegistration).not.toHaveBeenCalled(); } finally { vi.unstubAllGlobals(); }
});
it.each(["/auth/login", "/auth/logout", "/auth/claim"])("identity-changing %s waits for freeze acknowledgement", async path => {
  let port: MessagePort | undefined; const postMessage = vi.fn((_data: unknown, ports: MessagePort[]) => { port = ports[0]; });
  vi.stubGlobal("navigator", { serviceWorker: { getRegistration: vi.fn().mockResolvedValue({ scope: `${location.origin}/firebase-alerts/`, active: { scriptURL: `${location.origin}/firebase-alerts-sw.js`, postMessage } }) } });
  try { let done = false; const pending = freezeBeforeAuthMutation(path, "POST").then(() => { done = true; });
    await waitFor(() => expect(postMessage).toHaveBeenCalled()); expect(done).toBe(false); port!.postMessage({ ok: true }); await pending; expect(done).toBe(true);
  } finally { vi.unstubAllGlobals(); }
});
