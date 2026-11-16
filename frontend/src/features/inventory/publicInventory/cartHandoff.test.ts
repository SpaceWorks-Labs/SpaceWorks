import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { clearStashedCart, readStashedCart, safeReturnPath, stashCartForSignIn } from "./cartHandoff";
import { useInventoryCart } from "./useInventoryCart";

afterEach(() => { window.sessionStorage.clear(); window.history.replaceState(null, "", "/"); });

describe("Sign in to borrow cart handoff (0.12.0 row 29)", () => {
  it("restores the stashed cart on the same page, once", () => {
    window.history.replaceState(null, "", "/m/forge/inventory");
    stashCartForSignIn([{ productId: 4, name: "Drill", quantity: 2 }]);
    const { result, unmount } = renderHook(() => useInventoryCart());
    expect(result.current.selectedItems).toEqual([{ productId: 4, name: "Drill", quantity: 2 }]);
    unmount();
    // Read back once: a later visit starts empty.
    expect(renderHook(() => useInventoryCart()).result.current.selectedItems).toEqual([]);
  });

  it("keeps carts per page and ignores malformed rows", () => {
    stashCartForSignIn([{ productId: 1, name: "Saw", quantity: 1 }], "/m/a/inventory");
    expect(readStashedCart("/m/b/inventory")).toEqual({});
    window.sessionStorage.setItem("spaceworks.publicCart.handoff:/m/c/inventory",
      JSON.stringify([{ productId: "x", name: "Bad", quantity: 1 }, { productId: 2, name: "Glue", quantity: 500 }]));
    expect(readStashedCart("/m/c/inventory")).toEqual({ 2: { productId: 2, name: "Glue", quantity: 99 } });
    window.sessionStorage.setItem("spaceworks.publicCart.handoff:/m/d/inventory", "{not json");
    expect(readStashedCart("/m/d/inventory")).toEqual({});
    clearStashedCart("/m/a/inventory");
    expect(readStashedCart("/m/a/inventory")).toEqual({});
  });

  it("does not stash an empty cart", () => {
    stashCartForSignIn([], "/m/e/inventory");
    expect(window.sessionStorage.length).toBe(0);
  });

  it("accepts only same-origin return paths", () => {
    expect(safeReturnPath("/m/forge/inventory?category=3")).toBe("/m/forge/inventory?category=3");
    for (const bad of [null, "", "https://evil.test/x", "//evil.test/x", "/\\evil.test", "javascript:alert(1)", "m/forge"]) {
      expect(safeReturnPath(bad)).toBeUndefined();
    }
  });

  it("rejects targets that only become protocol-relative after normalization", () => {
    for (const bad of ["/.//evil.test/phish", "/%2e//evil.test/phish", "/%2E//evil.test", "/a/..//evil.test/phish",
      "/./\\evil.test", "/a/../\\evil.test", "/a/b/../..//evil.test"]) {
      expect(safeReturnPath(bad)).toBeUndefined();
    }
  });

  it("still normalizes harmless dot segments to a same-origin path", () => {
    expect(safeReturnPath("/m/./forge/../forge/inventory?x=1#top")).toBe("/m/forge/inventory?x=1#top");
    expect(safeReturnPath("/a/../member")).toBe("/member");
  });
});
