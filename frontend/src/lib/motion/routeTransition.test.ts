import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { canTransitionRoute, isSamePage, navigateWithTransition, replayRouteEnter, routeDirection, settleRouteTransition } from "./routeTransition";

type Doc = { startViewTransition?: unknown };
const doc = document as unknown as Doc;
const reduced = (value: boolean) => vi.stubGlobal("matchMedia", (query: string) => ({ matches: value && query.includes("reduce") }));

function supportViewTransitions() {
  const start = vi.fn((update: () => Promise<void> | void) => {
    void update();
    return { finished: Promise.resolve() };
  });
  doc.startViewTransition = start;
  return start;
}

describe("route transitions", () => {
  beforeEach(() => { vi.useFakeTimers(); reduced(false); });
  afterEach(() => {
    settleRouteTransition();
    delete doc.startViewTransition;
    document.documentElement.removeAttribute("data-sw-vt");
    document.documentElement.removeAttribute("data-sw-nav");
    document.documentElement.className = "";
    document.body.innerHTML = "";
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("uses a View Transition, names the direction and commits inside it", () => {
    const start = supportViewTransitions();
    const commit = vi.fn();
    navigateWithTransition(commit, "/staff/inventory", "/staff/inventory/42");
    expect(start).toHaveBeenCalledTimes(1);
    expect(commit).toHaveBeenCalledTimes(1);
    expect(document.documentElement.getAttribute("data-sw-vt")).toBe("route");
    expect(document.documentElement.getAttribute("data-sw-nav")).toBe("forward");
  });

  it("releases the transition once the new location rendered, and never waits longer than the safety timer", () => {
    supportViewTransitions();
    navigateWithTransition(vi.fn(), "/a", "/b");
    expect(settleRouteTransition()).toBe(true);
    expect(settleRouteTransition()).toBe(false);
    navigateWithTransition(vi.fn(), "/a", "/c");
    vi.advanceTimersByTime(200);
    expect(settleRouteTransition()).toBe(false);
  });

  it("falls back to a plain navigation when View Transitions are unsupported", () => {
    const commit = vi.fn();
    navigateWithTransition(commit, "/a", "/b");
    expect(commit).toHaveBeenCalledTimes(1);
    expect(document.documentElement.hasAttribute("data-sw-vt")).toBe(false);
  });

  it("skips the transition for reduced motion", () => {
    const start = supportViewTransitions();
    reduced(true);
    const commit = vi.fn();
    navigateWithTransition(commit, "/a", "/b");
    expect(start).not.toHaveBeenCalled();
    expect(commit).toHaveBeenCalledTimes(1);
  });

  it("skips same-page changes (search and hash) and other origins", () => {
    const start = supportViewTransitions();
    expect(isSamePage("/staff?tab=a", "/staff?tab=b#x")).toBe(true);
    expect(canTransitionRoute("/staff?tab=a", "/staff?tab=b")).toBe(false);
    expect(canTransitionRoute("/a", "https://example.org/b")).toBe(false);
    const commit = vi.fn();
    navigateWithTransition(commit, "/staff", "/staff#panel");
    expect(start).not.toHaveBeenCalled();
    expect(commit).toHaveBeenCalledTimes(1);
  });

  it("does not start while a theme switch owns the page snapshot", () => {
    supportViewTransitions();
    document.documentElement.classList.add("sw-theme-reveal-soft");
    expect(canTransitionRoute("/a", "/b")).toBe(false);
  });

  it("still navigates if startViewTransition throws", () => {
    doc.startViewTransition = () => { throw new Error("nope"); };
    const commit = vi.fn();
    navigateWithTransition(commit, "/a", "/b");
    expect(commit).toHaveBeenCalledTimes(1);
    expect(document.documentElement.hasAttribute("data-sw-vt")).toBe(false);
  });

  it("derives the direction from path depth, and only fades on kiosk screens", () => {
    expect(routeDirection("/staff", "/staff/inventory")).toBe("forward");
    expect(routeDirection("/staff/inventory/42", "/staff/inventory")).toBe("back");
    expect(routeDirection("/staff/inventory", "/staff/requests")).toBe("lateral");
    document.body.innerHTML = '<div class="sw-kiosk"></div>';
    expect(routeDirection("/staff", "/staff/inventory")).toBe("fade");
  });

  it("replays the CSS fade-in on the content region, except under reduced motion", () => {
    document.body.innerHTML = "<main data-sw-main></main>";
    const region = document.querySelector("[data-sw-main]")!;
    replayRouteEnter("back");
    expect(region.classList.contains("sw-route-enter")).toBe(true);
    expect(region.getAttribute("data-sw-enter")).toBe("back");
    region.className = "";
    reduced(true);
    replayRouteEnter("forward");
    expect(region.classList.contains("sw-route-enter")).toBe(false);
  });
});
