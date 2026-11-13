import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NotFoundPage } from "../../features/NotFoundPage";
import { DelightProvider } from "./DelightProvider";
import { NotFoundPatch, PATCH } from "./NotFoundPatch";

function motion(reduced: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduced && query.includes("reduce"), media: query,
    addEventListener() {}, removeEventListener() {} }));
}
const pet = (container: HTMLElement) => container.querySelector<HTMLElement>("[data-patch-pet]")!;
const body = (container: HTMLElement) => container.querySelector<HTMLElement>(".sw-patch-pet-body")!;
const sprite = (container: HTMLElement) => container.querySelector<HTMLElement>(".sw-patch-pet-sprite")!;
const offset = (container: HTMLElement) => Number(body(container).style.transform.match(/translateX\((.+)px\)/)![1]);
const frames = (ms: number) => act(() => { for (let t = 0; t < ms; t += 16) vi.advanceTimersByTime(16); });

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame", "setTimeout", "clearTimeout", "Date", "performance"] });
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1000 });
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); document.documentElement.classList.remove("dark"); });

describe("NotFoundPatch", () => {
  it("is decorative: hidden from assistive tech and inside a no-pointer strip", () => {
    motion(false);
    const { container } = render(<NotFoundPatch />);
    expect(pet(container)).toHaveAttribute("aria-hidden", "true");
    expect(pet(container)).toHaveClass("sw-patch-pet");
    expect(container.querySelector("img")).toBeNull();
  });

  it("switches to the approved left sheet when heading left, and back", () => {
    motion(false);
    const { container } = render(<NotFoundPatch />);
    frames(32);
    expect(body(container)).toHaveAttribute("data-facing", "right");
    expect(sprite(container).style.backgroundImage).toContain(PATCH.walkRight.light);
    fireEvent.pointerMove(window, { clientX: 5 });
    expect(body(container)).toHaveAttribute("data-facing", "left");
    expect(sprite(container).style.backgroundImage).toContain(PATCH.walkLeft.light);
    frames(400);
    const before = offset(container);
    expect(before).toBeLessThan(150); // trotted left from 15% of the width
    fireEvent.pointerDown(window, { clientX: 900 });
    expect(body(container)).toHaveAttribute("data-facing", "right");
    expect(sprite(container).style.backgroundImage).toContain(PATCH.walkRight.light);
    frames(400);
    expect(offset(container)).toBeGreaterThan(before);
  });

  it("leaves a few paw prints and naps on frame 6 with a z when left alone", () => {
    motion(false);
    vi.spyOn(Math, "random").mockReturnValue(0.99);
    const { container } = render(<NotFoundPatch />);
    frames(16);
    fireEvent.pointerMove(window, { clientX: 950 });
    frames(5000);
    const prints = container.querySelectorAll(".sw-patch-print");
    expect(prints.length).toBeGreaterThan(0);
    expect(prints.length).toBeLessThanOrEqual(6);
    frames(16000);
    expect(body(container)).toHaveAttribute("data-napping");
    expect(screen.getByText("z")).toBeInTheDocument();
    expect(body(container).style.getPropertyValue("--sw-patch-frame")).toBe("-640px");
    fireEvent.pointerMove(window, { clientX: 100 });
    frames(32);
    expect(body(container)).not.toHaveAttribute("data-napping");
  });

  it("walks on the dark sticker sheets in dark mode, both ways", () => {
    motion(false);
    document.documentElement.classList.add("dark");
    const { container } = render(<NotFoundPatch />);
    frames(32);
    expect(sprite(container).style.backgroundImage).toContain(PATCH.walkRight.dark);
    fireEvent.pointerMove(window, { clientX: 5 });
    expect(sprite(container).style.backgroundImage).toContain(PATCH.walkLeft.dark);
    expect(container.querySelector(".sw-patch-plate")).toBeNull();
  });

  it("stays still under reduced motion", () => {
    motion(true);
    const { container } = render(<NotFoundPatch />);
    frames(500);
    fireEvent.pointerMove(window, { clientX: 5 });
    frames(20000);
    expect(body(container)).toHaveAttribute("data-facing", "right");
    expect(body(container).style.transform).toBe("translateX(-50%)");
    expect(body(container)).not.toHaveAttribute("data-napping");
    expect(container.querySelectorAll(".sw-patch-print")).toHaveLength(0);
  });
});

describe("NotFoundPage", () => {
  const page = (path: string, enabled: boolean) => render(<MemoryRouter initialEntries={[path]}>
    <DelightProvider enabled={enabled} artwork={{ tag: { light: "/tag.svg", dark: "/tag.svg" } }}><NotFoundPage /></DelightProvider></MemoryRouter>);

  it("replaces the tag art and the companion with Patch when delight is on", () => {
    motion(false);
    const { container } = page("/m/forge/nowhere", true);
    expect(container.querySelector("[data-patch-pet]")).not.toBeNull();
    expect(container.querySelector('img[src="/tag.svg"]')).toBeNull();
    expect(screen.queryByRole("button", { name: /workshop companion/i })).toBeNull();
    expect(screen.getByRole("heading", { name: "Loan slip not found" })).toBeInTheDocument();
  });

  it("stays plain with delight off and on kiosk or payment paths", () => {
    motion(false);
    const { container, unmount } = page("/nowhere", false);
    expect(container.querySelector("[data-patch-pet]")).toBeNull();
    unmount();
    for (const path of ["/kiosk/abc/nowhere", "/m/forge/payments/x"]) {
      const view = page(path, true);
      expect(view.container.querySelector("[data-patch-pet]")).toBeNull();
      view.unmount();
    }
  });
});
