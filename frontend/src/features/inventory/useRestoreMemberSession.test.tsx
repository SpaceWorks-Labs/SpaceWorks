import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const refresh = vi.hoisted(() => vi.fn());
const identity = vi.hoisted(() => ({ value: "auth_present" as string, listeners: new Set<() => void>(), hasToken: false }));
vi.mock("../../lib/api/sessionTokens", () => ({
  hasSessionIdentity: () => identity.hasToken,
  refreshAccessToken: refresh,
}));
vi.mock("../../lib/telemetry/sessionFence", () => ({
  browserIdentity: () => identity.value,
  subscribeBrowserIdentity: (listener: () => void) => { identity.listeners.add(listener); return () => identity.listeners.delete(listener); },
}));

import { useRestoreMemberSession } from "./useRestoreMemberSession";

describe("useRestoreMemberSession", () => {
  beforeEach(() => { refresh.mockReset(); refresh.mockResolvedValue(true); identity.value = "auth_present"; identity.hasToken = false; });

  it("refreshes once when the server reports a signed-in cookie and no token is in memory", async () => {
    renderHook(() => useRestoreMemberSession(true));
    await act(async () => { await Promise.resolve(); });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(refresh).toHaveBeenCalledWith("person");
  });

  it("never calls the refresh endpoint for an anonymous visitor", async () => {
    identity.value = "anonymous";
    renderHook(() => useRestoreMemberSession(true));
    await act(async () => { await Promise.resolve(); });
    expect(refresh).not.toHaveBeenCalled();
  });

  it("does nothing when disabled or when a token is already held", async () => {
    renderHook(() => useRestoreMemberSession(false));
    identity.hasToken = true;
    renderHook(() => useRestoreMemberSession(true));
    await act(async () => { await Promise.resolve(); });
    expect(refresh).not.toHaveBeenCalled();
  });
});
