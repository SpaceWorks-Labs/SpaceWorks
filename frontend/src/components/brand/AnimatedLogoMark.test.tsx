import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnimatedLogoMark } from "./AnimatedLogoMark";
import SpaceWorksLogo from "../SpaceWorksLogo";

afterEach(() => { cleanup(); Reflect.deleteProperty(window, "matchMedia"); vi.restoreAllMocks(); vi.useRealTimers(); document.documentElement.classList.remove("dark"); });
const css = readFileSync(resolve(__dirname, "animatedLogo.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
const link = (props: Parameters<typeof AnimatedLogoMark>[0]) => render(<a href="/"><AnimatedLogoMark {...props} /></a>);
const touch = () => { const event = new Event("pointerenter"); Object.defineProperty(event, "pointerType", { value: "touch" }); return event; };
const reduceMotion = () => Object.defineProperty(window, "matchMedia", { configurable: true, writable: true, value: (query: string) => ({
  matches: query.includes("reduce"), media: query, addEventListener() {}, removeEventListener() {},
}) });
const animationEnd = (target: Element, name: string) => {
  const event = new Event("animationend", { bubbles: true });
  Object.defineProperty(event, "animationName", { value: name });
  act(() => { target.dispatchEvent(event); });
};

describe("AnimatedLogoMark", () => {
  it("draws only the static master at rest: no artwork mounted, symbol paths tagged", () => {
    const { container } = render(<AnimatedLogoMark variant="symbol" size={48} />);
    expect(container.querySelector(".sw-logo-box")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector(".sw-box")).toBeNull();
    expect(container.querySelectorAll("svg[role=img] .sw-logo-sym").length).toBe(7);
  });
  it("overlays only the symbol of a lockup, leaving the wordmark path alone", () => {
    const { container } = render(<AnimatedLogoMark variant="horizontal" size={288} />);
    const paths = container.querySelectorAll("svg[role=img] path");
    expect(container.querySelectorAll("svg[role=img] .sw-logo-sym").length).toBe(paths.length - 1);
    expect(paths[paths.length - 1].classList.contains("sw-logo-sym")).toBe(false);
  });
  it("is not animated when SpaceWorksLogo is used directly", () => {
    const { container } = render(<SpaceWorksLogo variant="symbol" />);
    expect(container.querySelector(".sw-logo-box")).toBeNull();
  });
  it.each(["sw-boxh-w", "sw-box412h-w"])("%s: hover finishes even if the pointer leaves", name => {
    const { container } = link({ variant: "symbol", size: 48 });
    const anchor = container.querySelector("a")!;
    fireEvent.pointerEnter(anchor);
    const box = container.querySelector(".sw-box.hov");
    expect(box).not.toBeNull();
    expect(box?.classList.contains("loop")).toBe(false);
    expect(container.querySelector("[data-logo]")?.hasAttribute("data-logo-playing")).toBe(true);
    fireEvent.pointerLeave(anchor);
    fireEvent.pointerEnter(anchor);
    expect(container.querySelector(".sw-box.hov")).toBe(box); // still running, not restarted
    animationEnd(box!, name);
    expect(container.querySelector(".sw-box")).toBeNull();
    expect(container.querySelector("[data-logo]")?.hasAttribute("data-logo-playing")).toBe(false);
  });
  it("settles by timer if no animationend arrives", () => {
    vi.useFakeTimers();
    const { container } = link({ variant: "symbol", size: 48 });
    fireEvent.pointerEnter(container.querySelector("a")!);
    expect(container.querySelector(".sw-box.hov")).not.toBeNull();
    act(() => { vi.advanceTimersByTime(2600); });
    expect(container.querySelector(".sw-box")).toBeNull();
  });
  it("never starts from touch", () => {
    const { container } = link({ variant: "symbol", size: 48 });
    act(() => { container.querySelector("a")!.dispatchEvent(touch()); });
    expect(container.querySelector(".sw-box")).toBeNull();
  });
  it("starts on keyboard focus-visible but not on mouse focus", () => {
    const { container } = link({ variant: "symbol", size: 48 });
    const anchor = container.querySelector("a")!;
    const matches = vi.spyOn(Element.prototype, "matches").mockReturnValue(false);
    fireEvent.focusIn(anchor);
    expect(container.querySelector(".sw-box")).toBeNull();
    matches.mockReturnValue(true);
    fireEvent.focusIn(anchor);
    expect(container.querySelector(".sw-box.hov")).not.toBeNull();
  });
  it("does nothing under reduced motion", () => {
    reduceMotion();
    const { container } = link({ variant: "symbol", size: 48 });
    fireEvent.pointerEnter(container.querySelector("a")!);
    expect(container.querySelector(".sw-box")).toBeNull();
    expect(css).toMatch(/prefers-reduced-motion: reduce\) \{ \.sw-logo-box \{ display: none/);
  });
  it("follows the ground: dark gets the dark artwork class", () => {
    const { container } = link({ variant: "symbol", ground: "dark" });
    fireEvent.pointerEnter(container.querySelector("a")!);
    expect(container.querySelector(".sw-box")?.classList.contains("g-dark")).toBe(true);
  });
  it("keeps the reversed mark cream and preserves explicit mono marks", () => {
    const { container, rerender } = link({ variant: "symbol", ground: "dark" });
    expect(container.querySelector(".sw-logo-colour")).not.toBeNull();
    expect(css).not.toContain("#006E63");
    expect(css).not.toContain("#FF7447");
    rerender(<a href="/"><AnimatedLogoMark variant="symbol" ground="dark" oneColour /></a>);
    expect(container.querySelector(".sw-logo-mono")).not.toBeNull();
    expect(container.querySelector(".sw-logo-colour")).toBeNull();
    fireEvent.pointerEnter(container.querySelector("a")!);
    expect(container.querySelector(".sw-box.mono.g-dark")).not.toBeNull();
  });
  it("outlines the moving flaps in the colour behind the mark (the first opaque background up the tree)", () => {
    const { container } = render(<div style={{ backgroundColor: "rgb(223, 255, 143)" }}><span style={{ backgroundColor: "rgba(0, 0, 0, 0)" }}>
      <a href="/"><AnimatedLogoMark variant="symbol" size={48} /></a></span></div>);
    fireEvent.pointerEnter(container.querySelector("a")!);
    expect((container.querySelector(".sw-box") as HTMLElement).style.getPropertyValue("--sw-ground")).toBe("rgb(223, 255, 143)");
  });
  it("does not change the mark's size (the overlay is absolutely positioned inside the fixed box)", () => {
    expect(css).toMatch(/\.sw-logo-box \{[^}]*position: absolute/);
    const a = render(<SpaceWorksLogo variant="stacked" size={180} />).container.querySelector("svg")!.getAttribute("width");
    cleanup();
    const b = render(<AnimatedLogoMark variant="stacked" size={180} />).container.querySelector("svg[role=img]")!.getAttribute("width");
    expect(b).toBe(a);
  });
});
