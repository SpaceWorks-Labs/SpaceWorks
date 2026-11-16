import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { findLogoTarget, runSplash } from "./splash";

const rect = (left: number, top: number, width: number, height: number) =>
  ({ left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({}) }) as DOMRect;

function mountSplash() {
  document.body.innerHTML = `<div id="sw-splash"><div class="bg"></div><div class="mark"></div></div><div id="sw-splash-status" role="status"></div>`;
  document.querySelector<HTMLElement>(".mark")!.getBoundingClientRect = () => rect(672, 405, 96, 89);
}
function mountLogo(viewBoxWidth: number, box = rect(44, 20, 240, 40)) {
  const holder = document.createElement("a");
  holder.setAttribute("data-sw-logo-target", "");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  Object.defineProperty(svg, "viewBox", { value: { baseVal: { width: viewBoxWidth } } });
  svg.getBoundingClientRect = () => box;
  holder.append(svg);
  document.body.append(holder);
}
const animate = vi.fn((..._args: unknown[]) => ({ finished: Promise.resolve() }));
const rises = () => animate.mock.calls.filter(call => JSON.stringify(call[0]).includes("scale("));
function setReduced(reduced: boolean) {
  window.matchMedia = ((query: string) => ({ matches: reduced && query.includes("reduce"), media: query, addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
}
async function play(ms = 5000) {
  const done = runSplash();
  await vi.advanceTimersByTimeAsync(ms);
  await done;
}

beforeEach(() => {
  vi.useFakeTimers();
  animate.mockClear();
  (Element.prototype as unknown as { animate: typeof animate }).animate = animate;
  window.history.pushState({}, "", "/spaces");
  setReduced(false);
});
afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
  delete (Element.prototype as unknown as { animate?: unknown }).animate;
});

describe("findLogoTarget", () => {
  it("returns the whole svg for the stand-alone symbol", () => {
    mountLogo(136, rect(16, 12, 48, 44));
    expect(findLogoTarget()).toEqual({ left: 16, top: 12, width: 48, height: 44 });
  });
  it("returns only the symbol part (the left square) of a lockup", () => {
    mountLogo(360, rect(44, 20, 360, 58));
    const target = findLogoTarget()!;
    expect(target.left).toBe(44);
    expect(target.width).toBeCloseTo(61.85, 1);
    expect(target.height).toBeCloseTo(57.6, 1);
  });
  it("skips a hidden (zero-size) logo and returns null when there is none", () => {
    mountLogo(136, rect(0, 0, 0, 0));
    expect(findLogoTarget()).toBeNull();
  });
});

describe("runSplash", () => {
  it("does nothing when there is no splash (client-side navigations, second call)", async () => {
    document.body.innerHTML = "";
    await expect(runSplash()).resolves.toBeUndefined();
    expect(animate).not.toHaveBeenCalled();
  });

  it("rises into the navbar logo with no fade, then fades the backdrop and removes the splash", async () => {
    mountSplash(); mountLogo(136, rect(16, 12, 48, 44));
    await play(2000);
    const [rise] = rises();
    expect(JSON.stringify(rise[0])).toContain("translate(-656px, -393px)");
    expect((rise[0] as { opacity: number }[])[1].opacity).toBe(1);
    expect(rise[1]).toMatchObject({ duration: 520, fill: "forwards" });
    expect(animate.mock.calls.at(-1)![1]).toMatchObject({ duration: 200 });
    expect(document.getElementById("sw-splash")).toBeNull();
    expect(document.getElementById("sw-splash-status")).toBeNull();
    await runSplash(); // a second call is a no-op
  });

  it("on a hub page with no navbar logo rises to the top centre while fading, after waiting for the logo", async () => {
    mountSplash();
    await play(6000);
    const [rise] = rises();
    expect((rise[0] as { opacity: number }[])[1].opacity).toBe(0);
    expect(document.getElementById("sw-splash")).toBeNull();
  });

  it("on a non-hub page does not wait for a logo: it rises to the top centre and fades", async () => {
    window.history.pushState({}, "", "/admin");
    mountSplash(); mountLogo(136, rect(16, 12, 48, 44));
    await play(1800);
    const [rise] = rises();
    expect((rise[0] as { opacity: number }[])[1].opacity).toBe(0);
    expect(document.getElementById("sw-splash")).toBeNull();
  });

  it("under reduced motion keeps the still logo: no wait, no rise, a quick fade", async () => {
    setReduced(true);
    mountSplash(); mountLogo(136, rect(16, 12, 48, 44));
    await play(0);
    expect(rises()).toHaveLength(0);
    expect(animate.mock.calls[0][1]).toMatchObject({ duration: 150 });
    expect(document.getElementById("sw-splash")).toBeNull();
  });

  it("still removes itself when the browser cannot animate", async () => {
    delete (Element.prototype as unknown as { animate?: unknown }).animate;
    mountSplash();
    await play();
    expect(document.getElementById("sw-splash")).toBeNull();
  });
});
