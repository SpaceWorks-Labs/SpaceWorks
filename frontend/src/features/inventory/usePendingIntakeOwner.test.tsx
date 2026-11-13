import { act, renderHook } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { usePendingIntakeOwner } from "./usePendingIntakeOwner";

const state = vi.hoisted(() => ({ owner: "1", listener: undefined as undefined | ((context: string) => void) }));
vi.mock("../../lib/api/sessionContext", () => ({ onSessionCleared: (listener: (context: string) => void) => { state.listener = listener; return () => { state.listener = undefined; }; } }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionOwner: () => state.owner }));
vi.mock("./useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: state.owner }) }));

it("keeps same-owner intent, retires old scope, and never clears the new scope", () => {
  state.owner = "1";
  const { result, rerender } = renderHook(({ scope }) => usePendingIntakeOwner(scope), { initialProps: { scope: "a" } });
  const old = result.current;
  const body = { operation_id: "one", event_registration_id: null, booking_token: null, requested_for: "work", items: [{ product_id: 1, quantity: 1 }] };
  old.begin("a", body); act(() => { state.listener?.("person"); });
  expect(old.current("a")).toEqual(body);
  rerender({ scope: "b" });
  const next = result.current; const newer = { ...body, operation_id: "two" }; next.begin("b", newer);
  expect(old.current("a")).toBeUndefined(); old.retire("a");
  expect(next.current("b")).toEqual(newer);
  act(() => { state.owner = "2"; state.listener?.("person"); });
  expect(next.current("b")).toBeUndefined();
});
