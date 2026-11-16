import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { KIOSK_IDLE_RESET_MS, useIdleReset } from "./kioskSession";

afterEach(() => vi.useRealTimers());
it("warns ten seconds before the existing idle deadline and keeps working on intent", () => {
  vi.useFakeTimers();
  const reset = vi.fn();
  const { result, unmount } = renderHook(() => useIdleReset(true, undefined, reset));
  act(() => vi.advanceTimersByTime(KIOSK_IDLE_RESET_MS - 10_000));
  expect(result.current.seconds).toBe(10);
  expect(reset).not.toHaveBeenCalled();
  act(() => result.current.onKeep());
  expect(result.current.seconds).toBeNull();
  act(() => vi.advanceTimersByTime(KIOSK_IDLE_RESET_MS));
  expect(reset).toHaveBeenCalledOnce();
  unmount();
});
it("never extends the server-owned lease when the warning is dismissed", () => {
  vi.useFakeTimers();
  const reset = vi.fn();
  const expiry = new Date(Date.now() + 8_000).toISOString();
  const { result, unmount } = renderHook(() => useIdleReset(true, expiry, reset));
  act(() => vi.advanceTimersByTime(3_000));
  act(() => result.current.onKeep());
  act(() => vi.advanceTimersByTime(5_000));
  expect(reset).toHaveBeenCalledOnce();
  unmount();
});
