import { act, renderHook } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { PendingIntake, type SelfBody } from "./contextualIntake";
import { useContextualIntent } from "./useContextualIntent";

const api = vi.hoisted(() => ({ member: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: api.member, staffRequest: vi.fn() }));
const fields = { requested_for: "work", items: [{ product_id: 1, quantity: 1 }] };
const result = { kind: "consumable_plan", plan_id: 1, replayed: false };

it("shares in-flight state across a closed and reopened form, then commits exactly once", async () => {
  let resolve!: (value: unknown) => void;
  api.member.mockReset(); api.member.mockImplementation(() => new Promise(done => { resolve = done; }));
  const owner = new PendingIntake<SelfBody>(); const success = vi.fn();
  const make = () => useContextualIntent("scope", "forge", owner, vi.fn(), vi.fn(), () => true, success);
  const first = renderHook(make); let pending!: Promise<unknown>;
  act(() => { pending = first.result.current.begin(fields, null, null); });
  first.unmount(); const replacement = renderHook(make);
  expect(replacement.result.current.state).toBe("sending");
  await act(async () => { await replacement.result.current.retry(); });
  expect(api.member).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(result); await pending; });
  expect(success).toHaveBeenCalledTimes(1); expect(replacement.result.current.state).toBe("idle");
});

it("does not apply an old success after retirement or a newer operation", async () => {
  let resolve!: (value: unknown) => void;
  api.member.mockReset(); api.member.mockImplementation(() => new Promise(done => { resolve = done; }));
  const owner = new PendingIntake<SelfBody>(); const success = vi.fn();
  const hook = renderHook(() => useContextualIntent("scope", "forge", owner, vi.fn(), vi.fn(), () => true, success));
  let pending!: Promise<unknown>; act(() => { pending = hook.result.current.begin(fields, null, null); });
  act(() => { owner.retire("scope"); owner.begin("scope", { ...fields, operation_id: "new", event_registration_id: null, booking_token: null }); });
  await act(async () => { resolve(result); await pending; });
  expect(success).not.toHaveBeenCalled(); expect(owner.current("scope")?.operation_id).toBe("new");
});
