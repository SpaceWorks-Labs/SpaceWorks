import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { transitionTheme } from "./themeTransition";

const root = document.documentElement;

beforeEach(() => {
  root.className = "";
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => {
  vi.unstubAllGlobals();
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: undefined });
});

function fakeTransition() {
  let finish!: () => void;
  const finished = new Promise<void>(resolve => { finish = resolve; });
  const start = vi.fn((update: () => void) => { update(); return { ready: Promise.resolve(), finished }; });
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: start });
  return { start, finish: () => finish() };
}

it("grows the new theme from the toggle and holds the last frame", async () => {
  const animate = vi.fn();
  Object.defineProperty(root, "animate", { configurable: true, value: animate });
  const { start, finish } = fakeTransition();
  const toggle = document.createElement("button");
  toggle.getBoundingClientRect = () => ({ left: 10, top: 20, width: 20, height: 20 }) as DOMRect;

  transitionTheme("dark", toggle);
  expect(start).toHaveBeenCalledOnce();
  expect(root.classList.contains("dark")).toBe(true);
  expect(root.classList.contains("sw-theme-reveal") || root.classList.contains("sw-theme-reveal-soft")).toBe(true);
  expect(root.style.getPropertyValue("--sw-reveal-x")).toBe("20px");
  await Promise.resolve();
  await Promise.resolve();
  const [, options] = animate.mock.calls[0];
  expect(options).toMatchObject({ duration: 720, fill: "forwards", pseudoElement: "::view-transition-new(root)" });

  finish();
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(root.classList.contains("sw-theme-reveal")).toBe(false);
  expect(root.classList.contains("sw-theme-reveal-soft")).toBe(false);
  expect(root.style.getPropertyValue("--sw-reveal-x")).toBe("");
});

it("switches instantly with reduced motion", () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  const { start } = fakeTransition();
  transitionTheme("dark");
  expect(root.classList.contains("dark")).toBe(true);
  expect(start).not.toHaveBeenCalled();
});

it("still applies the theme when the transition throws", () => {
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: () => { throw new Error("busy"); } });
  transitionTheme("dark");
  expect(root.classList.contains("dark")).toBe(true);
  expect(root.classList.contains("sw-theme-reveal")).toBe(false);
});
