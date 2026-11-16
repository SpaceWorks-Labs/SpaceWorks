import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useMemberReturn } from "./useMemberReturn";

afterEach(() => { window.sessionStorage.clear(); });

const render = (next: string, unauthenticated = true) => {
  const openSignIn = vi.fn();
  const search = new URLSearchParams({ next });
  const { result } = renderHook(() => useMemberReturn(search, { unauthenticated, signedIn: false, openSignIn }));
  return { result, openSignIn };
};

describe("member ?next= return (open-redirect guard)", () => {
  it("opens sign-in and returns to a same-origin path", () => {
    const { result, openSignIn } = render("/m/forge/inventory?category=3");
    expect(result.current.returnTo).toBe("/m/forge/inventory?category=3");
    expect(result.current.afterSignIn()).toBe("/m/forge/inventory?category=3");
    expect(openSignIn).toHaveBeenCalledTimes(1);
  });

  it.each(["/.//evil.test/phish", "/%2e//evil.test/phish", "/a/..//evil.test/phish", "//evil.test", "https://evil.test"])(
    "never returns to %s, which normalizes off-site", (next) => {
      const { result, openSignIn } = render(next);
      expect(result.current.returnTo).toBeUndefined();
      expect(result.current.afterSignIn()).toBeUndefined();
      expect(openSignIn).not.toHaveBeenCalled();
    },
  );
});
