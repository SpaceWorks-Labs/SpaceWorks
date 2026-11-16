import { beforeEach, expect, it, vi } from "vitest";
import { PendingIntake, submitContextualSelf, submitContextualStaff, type SelfBody } from "./contextualIntake";
const mock = vi.hoisted(() => ({ member: vi.fn(), staff: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: mock.member, staffRequest: mock.staff }));
beforeEach(() => { mock.member.mockReset(); mock.staff.mockReset(); });
const body: SelfBody = { operation_id: "11111111-1111-4111-8111-111111111111", event_registration_id: 3, booking_token: "22222222-2222-4222-8222-222222222222", items: [{ product_id: 1, quantity: 1 }], requested_for: "Workshop" };
it("notifies retained subscribers on completion but never clears a newer operation", () => {
  const pending = new PendingIntake<SelfBody>(); const notify = vi.fn(); const unsubscribe = pending.subscribe(notify);
  const first = pending.begin("scope", body); pending.clear();
  const next = pending.begin("scope", { ...body, operation_id: "33333333-3333-4333-8333-333333333333" });
  expect(pending.complete("scope", first)).toBe(false); expect(pending.current("scope")).toEqual(next);
  expect(pending.complete("scope", next)).toBe(true); expect(pending.current("scope")).toBeUndefined();
  expect(notify).toHaveBeenCalledTimes(4); unsubscribe();
});
it("keeps the original request after an uncertain response and conceals it across scope changes", () => {
  const pending = new PendingIntake<SelfBody>();
  pending.begin("actor-a:tenant-1", body); body.items![0].quantity = 2;
  expect(pending.current("actor-a:tenant-1")?.items?.[0].quantity).toBe(1);
  expect(() => pending.begin("actor-a:tenant-1", body)).toThrow();
  expect(pending.current("actor-b:tenant-1")).toBeUndefined();
  pending.retire("actor-a:tenant-1");
  expect(pending.current("actor-a:tenant-1")).toBeUndefined();
  pending.clear();
});

it("recognizes a consumable plan without inventing a loan and rejects an untyped response", async () => {
  const kitBody: SelfBody = { operation_id: body.operation_id, event_registration_id: null, booking_token: null, requested_for: "Workshop", kit: { id: 7, version: 2 } };
  mock.member.mockResolvedValueOnce({ kind: "consumable_plan", plan_id: 8, replayed: false });
  expect(await submitContextualSelf("space", kitBody)).toEqual({ kind: "consumable_plan", plan_id: 8, replayed: false });
  expect(JSON.parse(mock.member.mock.calls[0][1].body)).toMatchObject({ kit: { id: 7, version: 2 } });
  expect(JSON.parse(mock.member.mock.calls[0][1].body)).not.toHaveProperty("items");
  mock.member.mockResolvedValueOnce({ public_token: "token", status: "pending_approval", replayed: false });
  await expect(submitContextualSelf("space", kitBody)).rejects.toThrow("Invalid request response.");
});
it("sends the booking UUID only in the authenticated body", async () => {
  mock.member.mockResolvedValue({ kind: "request", public_token: "token", status: "pending_approval", replayed: false });
  await submitContextualSelf("space", body);
  expect(mock.member.mock.calls[0][0]).toBe("/public/space/requests/contextual");
  expect(JSON.parse(mock.member.mock.calls[0][1].body).booking_token).toBe(body.booking_token);
  expect(mock.member.mock.calls[0][0]).not.toContain(body.booking_token);
});
it("refuses an arbitrary staff proposal without context", async () => {
  await expect(submitContextualStaff(1, { ...body, borrower_id: 5, event_registration_id: null, booking_id: null })).rejects.toThrow();
  expect(mock.staff).not.toHaveBeenCalled();
});
