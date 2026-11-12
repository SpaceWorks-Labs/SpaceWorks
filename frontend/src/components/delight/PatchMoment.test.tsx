import { act, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PatchMoment } from "./PatchMoment";

const original = { io: window.IntersectionObserver, matchMedia: window.matchMedia };
afterEach(() => {
  window.IntersectionObserver = original.io; window.matchMedia = original.matchMedia;
  document.documentElement.classList.remove("dark");
});
function media(reduce: boolean) {
  window.matchMedia = vi.fn((query: string) => ({ matches: query.includes("reduce") ? reduce : false, media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn() })) as never;
}
function observer() {
  const seen: IntersectionObserverCallback[] = [];
  window.IntersectionObserver = vi.fn(function (this: unknown, cb: IntersectionObserverCallback) {
    seen.push(cb); return { observe: vi.fn(), disconnect: vi.fn(), unobserve: vi.fn() };
  }) as never;
  return seen;
}

describe("PatchMoment", () => {
  it("is decorative and uses the shipped sheet for the theme, never a flip", () => {
    media(false); observer();
    const { container, unmount } = render(<PatchMoment />);
    const patch = container.querySelector<HTMLElement>("[data-patch-moment]")!;
    expect(patch).toHaveAttribute("aria-hidden", "true");
    expect(patch.style.backgroundImage).toContain("/brand/patch/patch-walk-right.webp");
    expect(patch.style.transform).toBe("");
    unmount();
    document.documentElement.classList.add("dark");
    const left = render(<PatchMoment facing="left" />).container.querySelector<HTMLElement>("[data-patch-moment]")!;
    expect(left.style.backgroundImage).toContain("/brand/patch/patch-walk-left-dark.webp");
  });

  it("trots once when it scrolls into view", () => {
    media(false);
    const seen = observer();
    const { container } = render(<PatchMoment />);
    const patch = container.querySelector("[data-patch-moment]")!;
    expect(patch).not.toHaveAttribute("data-trot");
    act(() => seen[0]([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver));
    expect(patch).toHaveAttribute("data-trot");
  });

  it("stays a still frame under reduced motion", () => {
    media(true);
    const seen = observer();
    const { container } = render(<PatchMoment />);
    expect(seen).toHaveLength(0);
    expect(container.querySelector("[data-patch-moment]")).not.toHaveAttribute("data-trot");
  });
});
