import { expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ request: vi.fn(), fid: vi.fn(), suspend: vi.fn(), resume: vi.fn(), token: vi.fn() }));
vi.mock("../../../lib/api", () => ({ memberRequest: mocks.request }));
vi.mock("../../../lib/api/sessionTokens", () => ({ getAccessToken: mocks.token }));
vi.mock("../../../lib/api/authFreeze", () => ({ suspendPushForRefresh: mocks.suspend, resumePushAfterRefresh: mocks.resume }));
vi.mock("./firebaseFid", () => ({ currentFirebaseFid: mocks.fid }));
vi.mock("./firebaseRegistration", () => ({ registerOwnFirebaseWorker: async () => ({ active: navigator.serviceWorker.controller }) }));
import { beginFirebaseBridge, disableFirebaseForSpace } from "./firebaseBridge";
const config = { apiKey: "public", authDomain: "auth.test", projectId: "project", appId: "app", messagingSenderId: "sender" };
it("revokes only the selected space and does not unregister a shared worker", async () => {
  const worker = { scriptURL: `${location.origin}/firebase-alerts-sw.js` };
  vi.stubGlobal("navigator", { serviceWorker: { controller: worker } }); mocks.fid.mockResolvedValue("synthetic-fid"); mocks.request.mockResolvedValue(undefined);
  try { await disableFirebaseForSpace(7, config, "public-vapid");
    expect(mocks.request).toHaveBeenCalledWith("/notifications/browser-firebase/7/challenge", expect.objectContaining({ method: "DELETE", body: JSON.stringify({ project_id: "project", fid: "synthetic-fid" }) }));
  } finally { vi.unstubAllGlobals(); }
});
it("restores a prior same-actor ticket after a failed additional-space setup", async () => {
  history.replaceState(null, "", "/firebase-alerts/setup");
  const worker = { scriptURL: `${location.origin}/firebase-alerts-sw.js` };
  vi.stubGlobal("Notification", { permission: "granted" }); vi.stubGlobal("navigator", { serviceWorker: { controller: worker } });
  const previous = { ticket: "opaque", ownerEpoch: "epoch", worker }; mocks.suspend.mockResolvedValue(previous); mocks.fid.mockRejectedValue(new Error("offline")); mocks.token.mockReturnValue("current-access"); mocks.resume.mockResolvedValue(undefined);
  try { await expect(beginFirebaseBridge(8, config, "public-vapid", vi.fn())).rejects.toThrow("offline"); expect(mocks.resume).toHaveBeenCalledWith(previous, "current-access"); }
  finally { vi.unstubAllGlobals(); }
});
