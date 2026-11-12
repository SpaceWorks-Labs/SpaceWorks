import { act, render, renderHook } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RANGES, clamp, sequenceFrame, sequenceProgress, smoothstep, useScrollSequence, zoomScale } from "./useScrollSequence";
import { useActiveStep, useRevealOnScroll } from "./useInView";

const G = { start: 700, rest: 150, distance: 1800, scale: 2.5, offset: 73 };

describe("sequence maths", () => {
  it("clamps and eases without overshoot", () => {
    expect([clamp(-1), clamp(0.4), clamp(3)]).toEqual([0, 0.4, 1]);
    expect([smoothstep(0), smoothstep(0.5), smoothstep(1), smoothstep(2)]).toEqual([0, 0.5, 1, 1]);
    for (let x = 0; x < 1; x += 0.1) expect(smoothstep(x + 0.1)).toBeGreaterThanOrEqual(smoothstep(x));
  });

  it("measures progress from where the scene pins under the header", () => {
    expect(sequenceProgress(73, G)).toBe(0);
    expect(sequenceProgress(73 - 900, G)).toBe(0.5);
    expect(sequenceProgress(-5000, G)).toBe(1);
    expect(sequenceProgress(0, { distance: 0, offset: 0 })).toBe(0);
  });

  it("starts with the copy in place, the console peeking and the overview hidden and inert", () => {
    const f = sequenceFrame(0, G);
    expect(f).toMatchObject({ copyY: -0, copyOpacity: 1, copyInert: false, stageY: 700, frameScale: 1, figureOpacity: 1,
      revealOpacity: 0, revealInert: true, backdropOpacity: 0 });
  });

  it("lifts the copy away, then rests the console in the middle before zooming", () => {
    const lifted = sequenceFrame(RANGES.lift[1], G);
    expect(lifted.copyOpacity).toBe(0);
    expect(lifted.copyInert).toBe(true);
    const rested = sequenceFrame(0.5, G);
    expect(rested.stageY).toBe(150);
    expect(rested.frameScale).toBe(1);
    expect(rested.figureInert).toBe(false);
  });

  it("ends zoomed through, the console faded and inert, and the overview in place", () => {
    const f = sequenceFrame(1, G);
    expect(f).toMatchObject({ frameScale: 2.5, figureOpacity: 0, figureInert: true, revealOpacity: 1, revealY: 0, revealScale: 1, revealInert: false });
  });

  it("scales so the zoom target's nearer edge passes the viewport, and refuses a target off-centre", () => {
    const frame = new DOMRect(100, 100, 1200, 500);
    const target = new DOMRect(320, 150, 660, 400); // centre (700, 350): 280 to the right edge, 200 to the top
    expect(zoomScale(frame, target, 1440, 828)).toBeCloseTo(Math.max(1440 / 560, 828 / 400) * 1.06);
    expect(zoomScale(frame, new DOMRect(900, 150, 100, 100), 1440, 828)).toBe(1);
  });
});

function media(matches: Record<string, boolean>) {
  window.matchMedia = vi.fn((query: string) => ({ matches: matches[query] ?? false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })) as never;
}

function Sequence() {
  const ref = useRef<HTMLDivElement>(null);
  useScrollSequence(ref);
  return <div ref={ref} data-testid="seq">
    {["scene", "copy", "stage", "frame", "figure", "content", "reveal", "backdrop"].map(key => <div key={key} data-seq={key} />)}
  </div>;
}

describe("useScrollSequence", () => {
  const original = { matchMedia: window.matchMedia, raf: window.requestAnimationFrame };
  let frames: FrameRequestCallback[] = [];
  beforeEach(() => {
    frames = [];
    window.requestAnimationFrame = vi.fn((cb: FrameRequestCallback) => { frames.push(cb); return frames.length; });
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(function (this: HTMLElement) {
      const key = this.dataset.seq ?? this.dataset.testid;
      return ({ scene: 828, copy: 400, frame: 500, seq: 2628 } as Record<string, number>)[key ?? ""] ?? 0;
    });
  });
  afterEach(() => {
    window.matchMedia = original.matchMedia;
    window.requestAnimationFrame = original.raf;
    vi.restoreAllMocks();
  });

  it("stays static under reduced motion", () => {
    media({ "(prefers-reduced-motion: reduce)": true, "(min-width: 768px)": true });
    const { getByTestId } = render(<Sequence />);
    expect(getByTestId("seq")).not.toHaveAttribute("data-animated");
  });

  it("stays static on phones", () => {
    media({ "(min-width: 768px)": false });
    const { getByTestId } = render(<Sequence />);
    expect(getByTestId("seq")).not.toHaveAttribute("data-animated");
  });

  it("pins on a wide screen, paints once per animation frame and marks hidden parts inert", () => {
    media({ "(min-width: 768px)": true });
    const { getByTestId } = render(<Sequence />);
    const seq = getByTestId("seq");
    expect(seq).toHaveAttribute("data-animated");
    const copy = seq.querySelector<HTMLElement>('[data-seq="copy"]')!, reveal = seq.querySelector<HTMLElement>('[data-seq="reveal"]')!;
    expect(reveal.inert).toBe(true); // first paint at progress 0
    vi.spyOn(seq, "getBoundingClientRect").mockReturnValue(new DOMRect(0, -5000, 1440, 2628));
    act(() => { window.dispatchEvent(new Event("scroll")); window.dispatchEvent(new Event("scroll")); });
    expect(frames).toHaveLength(1); // two scroll events, one frame
    act(() => frames[0](0));
    expect(copy.inert).toBe(true);
    expect(copy.style.opacity).toBe("0");
    expect(reveal.inert).toBe(false);
    expect(reveal.style.opacity).toBe("1");
    expect(seq).not.toHaveAttribute("data-moving"); // at rest: no will-change
  });

  it("falls back to static when the overview would not fit the screen", () => {
    media({ "(min-width: 768px)": true });
    vi.spyOn(HTMLElement.prototype, "scrollHeight", "get").mockImplementation(function (this: HTMLElement) {
      return this.dataset.seq === "reveal" ? 2000 : 0;
    });
    const { getByTestId } = render(<Sequence />);
    expect(getByTestId("seq")).not.toHaveAttribute("data-animated");
  });
});

describe("useActiveStep and useRevealOnScroll", () => {
  const original = { io: window.IntersectionObserver, matchMedia: window.matchMedia };
  let callbacks: IntersectionObserverCallback[] = [];
  const unobserve = vi.fn();
  beforeEach(() => {
    callbacks = [];
    window.IntersectionObserver = vi.fn(function (this: unknown, cb: IntersectionObserverCallback) {
      callbacks.push(cb);
      return { observe: vi.fn(), unobserve, disconnect: vi.fn() };
    }) as never;
    media({});
  });
  afterEach(() => { window.IntersectionObserver = original.io; window.matchMedia = original.matchMedia; });
  const hit = (target: Element, isIntersecting = true) => ({ target, isIntersecting }) as IntersectionObserverEntry;

  it("follows the step that crosses the middle band", () => {
    const list = document.createElement("ol");
    list.innerHTML = '<li data-step="0"></li><li data-step="1"></li><li data-step="2"></li>';
    const { result } = renderHook(() => useActiveStep({ current: list }));
    expect(result.current[0]).toBe(0);
    expect(window.IntersectionObserver).toHaveBeenCalledWith(expect.any(Function), { rootMargin: "-45% 0px -45% 0px" });
    act(() => callbacks[0]([hit(list.children[2])], {} as IntersectionObserver));
    expect(result.current[0]).toBe(2);
    act(() => callbacks[0]([hit(list.children[1], false)], {} as IntersectionObserver));
    expect(result.current[0]).toBe(2);
  });

  it("reveals each element once and only arms the hiding CSS when it can reveal", () => {
    const root = document.createElement("main");
    root.innerHTML = "<div data-reveal></div><div data-reveal></div>";
    renderHook(() => useRevealOnScroll({ current: root }));
    expect(root).toHaveAttribute("data-reveal-ready");
    act(() => callbacks[0]([hit(root.children[0])], {} as IntersectionObserver));
    expect(root.children[0]).toHaveAttribute("data-revealed");
    expect(root.children[1]).not.toHaveAttribute("data-revealed");
    expect(unobserve).toHaveBeenCalledWith(root.children[0]);
  });

  it("does nothing under reduced motion, so everything stays visible", () => {
    media({ "(prefers-reduced-motion: reduce)": true });
    const root = document.createElement("main");
    root.innerHTML = "<div data-reveal></div>";
    renderHook(() => useRevealOnScroll({ current: root }));
    expect(root).not.toHaveAttribute("data-reveal-ready");
    expect(callbacks).toHaveLength(0);
  });
});
