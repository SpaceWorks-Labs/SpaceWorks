import { afterEach, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken, staffRequest } from "./api";
import { setReauthenticationHandler } from "./api/reauthentication";

const token = (sid: string) => `header.${btoa(JSON.stringify({ user_id: 7, sid, surface: "staff" }))}.signature`;
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
let unregister: (() => void) | undefined;
afterEach(() => { unregister?.(); unregister = undefined; clearAccessToken(); vi.unstubAllGlobals(); });

it.each([
  ["/admin/spaces/9/staff-invites/", "POST"],
  ["/admin/booking-staff-grants/3/", "PATCH"],
  ["/admin/booking-staff-grants/3/revoke/", "POST"],
  ["/admin/booking-staff-invites/4/revoke/", "POST"],
  ["/admin/booking-staff-invites/redeem/", "POST"],
])("uses the shared step-up retry for %s", async (path, method) => {
  setAccessToken(token("session:current"));
  const verify = vi.fn().mockResolvedValue(true);
  unregister = setReauthenticationHandler(verify);
  const fetch = vi.fn().mockResolvedValueOnce(reply({ code: "recent_reauth_required" }, 403))
    .mockResolvedValueOnce(reply({ id: 3 }));
  vi.stubGlobal("fetch", fetch);
  expect(await staffRequest(path, { method, body: "{}" })).toEqual({ id: 3 });
  expect(verify).toHaveBeenCalledOnce();
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls[1][0]).toBe(fetch.mock.calls[0][0]);
  expect(fetch.mock.calls[1][1].body).toBe("{}");
});

it("does not replay a grant mutation into a different browser session", async () => {
  setAccessToken(token("session:original"));
  unregister = setReauthenticationHandler(async () => { setAccessToken(token("session:different")); return true; });
  const fetch = vi.fn().mockResolvedValue(reply({ code: "recent_reauth_required" }, 403));
  vi.stubGlobal("fetch", fetch);
  await expect(staffRequest("/admin/booking-staff-grants/3/revoke/", { method: "POST", body: "{}" })).rejects.toThrow();
  expect(fetch).toHaveBeenCalledOnce();
});

it("does not retry a resource permission denial as reauthentication", async () => {
  setAccessToken(token("session:current"));
  const verify = vi.fn().mockResolvedValue(true);
  unregister = setReauthenticationHandler(verify);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ detail: "Permission denied" }, 403)));
  await expect(staffRequest("/admin/booking-staff-grants/3/", { method: "PATCH", body: "{}" })).rejects.toThrow();
  expect(verify).not.toHaveBeenCalled();
});
