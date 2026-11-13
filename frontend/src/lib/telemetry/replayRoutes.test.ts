import { describe, expect, it } from "vitest";
import { safePage } from "./policy";
import { replayRoute } from "./replayRoutes";

describe("public replay route projection", () => {
  const url = (path: string) => new URL(path, window.location.origin);
  it.each(["/", "/m/demo", "/inventory", "/m/demo/inventory", "/events", "/m/demo/events", "/shop", "/m/demo/shop", "/bookings", "/m/demo/bookings", "/about"])("admits anonymous PostHog browse template %s", path => {
    expect(replayRoute("posthog", safePage(url(path)))).toBe(true);
  });
  it.each(["/items/1", "/events/123", "/shop/item", "/bookings/123", "/member", "/inventory?code=private", "/shop#private"])("denies private or unlisted detail %s", path => {
    expect(replayRoute("posthog", safePage(url(path)))).toBe(false);
  });
  it("keeps Clarity on About and declines other providers", () => {
    expect(replayRoute("clarity", safePage(url("/about")))).toBe(true);
    expect(replayRoute("clarity", safePage(url("/shop")))).toBe(false);
    expect(replayRoute("none", safePage(url("/")))).toBe(false);
  });
  it("denies credentials even on the same origin", () => {
    const target = new URL("/inventory", window.location.origin);
    target.username = "private-user"; target.password = "private-pass";
    expect(safePage(target)).toBeNull();
    expect(replayRoute("posthog", safePage(target))).toBe(false);
  });
});
