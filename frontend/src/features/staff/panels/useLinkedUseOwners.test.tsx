import { act, renderHook } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { expect, it, vi } from "vitest";
import { StaffListContext } from "../StaffListContext";
import { useLinkedUseOwners } from "./useLinkedUseOwners";

const state = vi.hoisted(() => ({ owner: "1", listener: undefined as undefined | ((context: string) => void) }));
vi.mock("../../../lib/api/sessionContext", () => ({ onSessionCleared: (fn: (context: string) => void) => { state.listener = fn; return () => {}; } }));
vi.mock("../../../lib/api/sessionTokens", () => ({ getSessionOwner: () => state.owner }));
vi.mock("../../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: state.owner }) }));
const wrapper = ({ children }: { children: ReactNode }) => createElement(StaffListContext.Provider, { value: { ownerName: "", canShare: false, actorId: 1 } }, children);
const body = { operation_id: "fixed", quantity: 1, note: "private", allocation_id: null, plan_id: 3 };

it("clears a retained intent reference when the semantic owner is retired", () => {
  state.owner = "1"; const { result } = renderHook(() => useLinkedUseOwners(108), { wrapper });
  const retained = result.current.owner(8); const scope = result.current.scope + ":8";
  retained.begin(scope, body); const notified = vi.fn(); retained.subscribe(notified);
  state.owner = "2"; act(() => state.listener?.("person"));
  expect(retained.current(scope)).toBeUndefined(); expect(notified).toHaveBeenCalledTimes(1);
});

it.each(["ordinary", "linked"])("blocks the opposite path while a deferred %s action is pending", async (kind) => {
  state.owner = "1"; const { result } = renderHook(() => useLinkedUseOwners(104), { wrapper });
  let done!: () => void; const pending = new Promise<void>(resolve => { done = resolve; });
  if (kind === "ordinary") {
    const release = result.current.beginOrdinary(8); expect(release).toBeTypeOf("function");
    const completion = pending.finally(() => release!(true));
    expect(result.current.acquire(8)).toBeUndefined();
    done(); await completion;
    const next = result.current.acquire(8); expect(next).toBeTypeOf("function"); next!();
  } else {
    const release = result.current.acquire(8); expect(release).toBeTypeOf("function");
    const completion = pending.finally(release);
    expect(result.current.beginOrdinary(8)).toBeUndefined();
    done(); await completion;
    const next = result.current.beginOrdinary(8); expect(next).toBeTypeOf("function"); next!(true);
  }
});

it("retains the same uncertain intent across unmount and same-owner refresh, but clears on identity loss", () => {
  state.owner = "1"; const first = renderHook(() => useLinkedUseOwners(105), { wrapper });
  const scope = first.result.current.scope + ":8";
  act(() => { first.result.current.owner(8).begin(scope, body); }); first.unmount();
  act(() => state.listener?.("person"));
  const next = renderHook(() => useLinkedUseOwners(105), { wrapper });
  expect(next.result.current.owner(8).current(scope)).toEqual(body);
  state.owner = "2"; act(() => state.listener?.("person"));
  expect(next.result.current.admitted()).toBe(false);
  expect(next.result.current.acquire(8)).toBeUndefined();
  state.owner = "1"; act(() => state.listener?.("person")); next.rerender();
  expect(next.result.current.owner(8).current(scope)).toBeUndefined();
  act(() => { next.result.current.owner(8).begin(scope, body); });
  state.owner = ""; act(() => state.listener?.("person"));
  state.owner = "1"; act(() => state.listener?.("person")); next.rerender();
  expect(next.result.current.owner(8).current(scope)).toBeUndefined();
});

it("retains an ordinary unknown across refresh and remount but retires it on owner loss", () => {
  state.owner = "1"; const first = renderHook(() => useLinkedUseOwners(106), { wrapper });
  const finish = first.result.current.beginOrdinary(9); expect(finish).toBeTypeOf("function");
  act(() => finish!(false)); first.unmount(); act(() => state.listener?.("person"));
  const next = renderHook(() => useLinkedUseOwners(106), { wrapper });
  expect(next.result.current.ordinaryUnknown(9)).toBe(true);
  expect(next.result.current.acquire(9)).toBeUndefined();
  expect(next.result.current.beginOrdinary(9)).toBeUndefined();
  state.owner = "2"; act(() => state.listener?.("person"));
  state.owner = "1"; act(() => state.listener?.("person")); next.rerender();
  expect(next.result.current.ordinaryUnknown(9)).toBe(false);
});

it("requires current audit authority and owner and preserves linked intent on recovery", () => {
  state.owner = "1"; const { result } = renderHook(() => useLinkedUseOwners(107), { wrapper });
  const scope = result.current.scope + ":9";
  result.current.owner(9).begin(scope, body);
  const finish = result.current.beginOrdinary(9); expect(finish).toBeTypeOf("function");
  expect(result.current.resolveOrdinary(9, true)).toBe(false);
  finish!(false);
  expect(result.current.resolveOrdinary(9, false)).toBe(false);
  state.owner = "2";
  expect(result.current.resolveOrdinary(9, true)).toBe(false);
  state.owner = "1";
  expect(result.current.resolveOrdinary(9, true)).toBe(true);
  expect(result.current.ordinaryUnknown(9)).toBe(false);
  expect(result.current.owner(9).current(scope)).toEqual(body);
});
