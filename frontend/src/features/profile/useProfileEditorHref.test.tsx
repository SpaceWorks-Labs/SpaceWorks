import { renderHook } from "@testing-library/react";
import { expect, it } from "vitest";
import { PROFILE_EDITOR_HREF, useProfileEditorHref } from "./useProfileEditorHref";

it("sends an owner to the one global profile editor", () => {
  expect(renderHook(() => useProfileEditorHref(true)).result.current.href).toBe("/member/profile");
  expect(PROFILE_EDITOR_HREF).toBe("/member/profile");
});

it("offers no editor link to anyone who is not the owner", () => {
  expect(renderHook(() => useProfileEditorHref(false)).result.current.href).toBeUndefined();
});
