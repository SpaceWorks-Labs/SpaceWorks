import { act, renderHook } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { useStaffIntakeOwners } from "./useStaffIntakeOwners";

const state = vi.hoisted(() => ({ owner: "1", listener: undefined as undefined | ((context: string) => void) }));
vi.mock("../../lib/api/sessionContext", () => ({ onSessionCleared: (listener: (context: string) => void) => { state.listener = listener; return () => { state.listener = undefined; }; } }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionOwner: () => state.owner }));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: state.owner }) }));
vi.mock("./StaffListContext", async () => { const React = await import("react"); return { StaffListContext: React.createContext({ actorId: 1 }) }; });

beforeEach(() => { state.owner = "1"; state.listener = undefined; });
const body = { operation_id: "one", event_registration_id: 1, booking_id: null, requested_for: "tools", items: [{ product_id: 1, quantity: 1 }] };

it("retires retained references only on an owner change, and old getters cannot access a new scope", () => {
  const { result, rerender } = renderHook(({ tenant }) => useStaffIntakeOwners(tenant), { initialProps: { tenant: 1 } });
  const oldGetter = result.current; const old = oldGetter("event"); old.begin("a", body);
  const notified = vi.fn(); old.subscribe(notified);
  act(() => { state.listener?.("person"); });
  expect(old.current("a")).toEqual(body); expect(notified).not.toHaveBeenCalled();
  act(() => { state.owner = "2"; state.listener?.("person"); });
  expect(old.current("a")).toBeUndefined(); expect(notified).toHaveBeenCalledTimes(1);
  rerender({ tenant: 2 });
  expect(result.current("event")).not.toBe(old);
  expect(() => oldGetter("event")).toThrow();
});

it("does not clear or notify on a scope read and only completes the exact active intent", () => {
  const { result } = renderHook(() => useStaffIntakeOwners(1));
  const owner = result.current("event"); const notified = vi.fn(); owner.subscribe(notified);
  owner.begin("a", body); notified.mockClear();
  expect(owner.current("other")).toBeUndefined(); expect(notified).not.toHaveBeenCalled();
  owner.clear(); const next = { ...body, operation_id: "two" }; owner.begin("a", next);
  expect(owner.complete("a", body)).toBe(false); expect(owner.current("a")).toEqual(next);
  expect(owner.complete("a", next)).toBe(true);
});
