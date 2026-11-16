// Decision 220(e): retire, key rotation, push and rehydrate answer 403 `recent_reauth_required`
// until the superadmin re-authenticates; the platform console's shared step-up prompt opens and
// the same request is replayed once on the same browser session.
import { afterEach, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken } from "../../../../lib/api";
import { setReauthenticationHandler } from "../../../../lib/api/reauthentication";
import { patch, post } from "../../platformParity/parityRequest";

const token = (sid: string) => `header.${btoa(JSON.stringify({ user_id: 1, sid, surface: "platform" }))}.signature`;
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
let unregister: (() => void) | undefined;
afterEach(() => { unregister?.(); unregister = undefined; clearAccessToken("platform"); vi.unstubAllGlobals(); });

const BASE = "/admin/platform/backup-destinations";

it.each([
  ["retire", () => post(`${BASE}/3/retire`)],
  ["push", () => post(`${BASE}/push`)],
  ["rehydrate", () => post("/admin/platform/backups/0b7c9f3e-0000-4000-8000-000000000001/rehydrate", { destination: 3 })],
  ["key rotation", () => patch(`${BASE}/3`, { access_key_id: "AKIANEW", secret_access_key: "new" })],
  ["retention edit", () => patch(`${BASE}/3`, { retention_days: 30 })],
  ["connection test", () => post(`${BASE}/3/test`)],
])("%s opens the step-up prompt and replays once", async (_name, send) => {
  setAccessToken(token("session:platform"), "platform");
  const verify = vi.fn().mockResolvedValue(true);
  unregister = setReauthenticationHandler(verify, "platform");
  const fetch = vi.fn().mockResolvedValueOnce(reply({ code: "recent_reauth_required" }, 403))
    .mockResolvedValueOnce(reply({ detail: "ok" }));
  vi.stubGlobal("fetch", fetch);
  expect(await send()).toEqual({ detail: "ok" });
  expect(verify).toHaveBeenCalledOnce();
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][0]).toBe(fetch.mock.calls[0][0]);
});

it("a declined prompt leaves the refusal for the dialog to show", async () => {
  setAccessToken(token("session:platform"), "platform");
  unregister = setReauthenticationHandler(vi.fn().mockResolvedValue(false), "platform");
  const fetch = vi.fn().mockResolvedValue(reply({ code: "recent_reauth_required" }, 403));
  vi.stubGlobal("fetch", fetch);
  await expect(post(`${BASE}/3/retire`)).rejects.toThrow();
  expect(fetch).toHaveBeenCalledOnce();
});
