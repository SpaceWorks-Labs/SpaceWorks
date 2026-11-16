import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render as rtlRender, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProgrammeDelight } from "../../features/events/programme/ProgrammeDelight";
import { LoanResult } from "../../features/loanDelight/LoanResult";
import { cachePolicy } from "../../swPolicy";
import { SpaceWorksLogo } from "../SpaceWorksLogo";
import { StaggerGroup } from "../layouts/StaggerGroup";
import { toastStore } from "../ui/toastStore";
import { BrandLoader, MoodGlyph } from "./Artwork";
import { Companion } from "./Companion";
import { DelightProvider } from "./DelightProvider";
import { LogoDelight } from "./LogoDelight";
import { confettiPalette, ReturnConfetti } from "./ReturnConfetti";
import { ResultPanel } from "../ui/ResultPanel";
import { LateShiftLine, SudoMake } from "./SneakyLines";

// ProgrammeDelight reads the showing space's features through TanStack Query.
const render = (ui: React.ReactElement) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(ui, { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
};
function motion(reduced: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduced && query.includes("reduce"), media: query,
    addEventListener() {}, removeEventListener() {} }));
}
const at = (path: string) => window.history.pushState({}, "", path);
beforeEach(() => { at("/m/forge/admin"); window.sessionStorage.clear(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); delete window.__TENANT__; document.documentElement.removeAttribute("data-sw-delight"); });
const delight = (children: React.ReactNode, eggs = true) => <DelightProvider enabled eggsEnabled={eggs}>{children}</DelightProvider>;

describe("Patch stays on the 404 page", () => {
  it("leaves every delight slot on the design-system SVG illustrations", () => {
    motion(false);
    window.__TENANT__ = { uiDelightEnabled: true };
    const { container } = render(<MemoryRouter initialEntries={["/m/forge"]}><ProgrammeDelight>
      <BrandLoader /><MoodGlyph mood="success" /><MoodGlyph mood="empty" /><LoanResult resultId="1" name="Drill" outcome="returned" />
    </ProgrammeDelight></MemoryRouter>);
    const sources = [...container.querySelectorAll("img")].map(img => img.getAttribute("src") ?? "");
    expect(sources.length).toBeGreaterThan(0);
    expect(sources.some(src => src.includes("/brand/patch/"))).toBe(false);
    expect(container.querySelector("[data-patch]")).toBeNull();
  });

  it("keeps the companion on its SVG art too", () => {
    motion(false);
    const { container } = render(delight(<Companion />));
    fireEvent.click(screen.getByRole("button", { name: /workshop companion/i }));
    expect(container.innerHTML).not.toContain("/brand/patch/");
  });

  it("never serves Patch from the kiosk cache", () => {
    const request = (path: string) => ({ url: `https://x.test${path}`, method: "GET", mode: "no-cors" as RequestMode, headers: new Headers() });
    const precache = new Set(["/brand/patch/patch-walk-right.webp", "/brand/icon-192.png"]);
    expect(cachePolicy(request("/brand/patch/patch-walk-right.webp"), "https://x.test", precache)).toBe("network");
    expect(cachePolicy(request("/brand/icon-192.png"), "https://x.test", precache)).toBe("static");
  });
});

describe("box logo unfold", () => {
  it("tags exactly four flaps in every master, without touching fills or paths", () => {
    for (const props of [{ variant: "symbol" as const }, { variant: "stacked" as const }, { variant: "horizontal" as const }, { variant: "symbol" as const, ground: "dark" as const }]) {
      const { container, unmount } = render(<SpaceWorksLogo {...props} />);
      const flaps = [...container.querySelectorAll(".sw-logo-flap")];
      expect(flaps.map(flap => flap.getAttribute("class"))).toEqual(["tl", "tr", "bl", "br"].map(key => `sw-logo-flap sw-logo-flap-${key}`));
      flaps.forEach(flap => { expect(flap.getAttribute("style")).toBeNull(); expect(flap.getAttribute("transform")).toBeNull(); });
      unmount();
    }
  });

  it("marks the page and springs on click only when delight is on, motion is allowed and the path is not excluded", () => {
    motion(false);
    const { container, rerender } = render(delight(<><LogoDelight pathname="/m/forge" /><SpaceWorksLogo variant="symbol" /></>));
    expect(document.documentElement).toHaveAttribute("data-sw-delight");
    fireEvent.click(container.querySelector("[data-logo]")!);
    expect(container.querySelector("[data-logo]")).toHaveAttribute("data-logo-pop");
    rerender(delight(<><LogoDelight pathname="/m/forge/kiosk/abc" /><SpaceWorksLogo variant="symbol" /></>));
    expect(document.documentElement).not.toHaveAttribute("data-sw-delight");
    rerender(<DelightProvider enabled={false}><LogoDelight pathname="/m/forge" /></DelightProvider>);
    expect(document.documentElement).not.toHaveAttribute("data-sw-delight");
  });

  it("does not spring under reduced motion, but still counts clicks", () => {
    motion(true);
    const counted = vi.fn();
    const { container } = render(delight(<><LogoDelight pathname="/m/forge" onLogoClick={counted} /><SpaceWorksLogo variant="symbol" /></>));
    fireEvent.click(container.querySelector("[data-logo]")!);
    expect(container.querySelector("[data-logo]")).not.toHaveAttribute("data-logo-pop");
    expect(counted).toHaveBeenCalledTimes(1);
  });

  it("opens Maker mode after seven logo clicks", () => {
    motion(false);
    window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: true };
    const { container } = render(<MemoryRouter initialEntries={["/m/forge"]}><ProgrammeDelight><SpaceWorksLogo variant="symbol" /></ProgrammeDelight></MemoryRouter>);
    const logo = container.querySelector("[data-logo]")!;
    for (let click = 0; click < 6; click += 1) fireEvent.click(logo);
    expect(screen.queryByText(/Workshop grid enabled/)).toBeNull();
    fireEvent.click(logo);
    expect(screen.getByRole("status")).toHaveTextContent("Maker mode on");
    expect(screen.getByRole("complementary", { name: "Built by makers" })).toBeInTheDocument();
  });

  const shell = (path: string) => render(<MemoryRouter initialEntries={[path]}><ProgrammeDelight><SpaceWorksLogo variant="symbol" /></ProgrammeDelight></MemoryRouter>);
  it("keeps counting across the page load a logo link causes, and opens Maker mode where it lands", () => {
    motion(false);
    window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: true };
    const first = shell("/m/forge/admin");
    for (let click = 0; click < 4; click += 1) fireEvent.click(first.container.querySelector("[data-logo]")!);
    first.unmount(); // the link navigated: a fresh page
    const second = shell("/m/forge");
    for (let click = 0; click < 3; click += 1) fireEvent.click(second.container.querySelector("[data-logo]")!);
    second.unmount(); // the seventh click navigated again
    shell("/");
    expect(screen.getByRole("complementary", { name: "Built by makers" })).toBeInTheDocument();
  });

  it("opens on the landed page under React's development double mount too", () => {
    motion(false);
    window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: true };
    const first = shell("/m/forge");
    for (let click = 0; click < 7; click += 1) fireEvent.click(first.container.querySelector("[data-logo]")!);
    first.unmount();
    render(<StrictMode><MemoryRouter initialEntries={["/"]}><ProgrammeDelight><SpaceWorksLogo variant="symbol" /></ProgrammeDelight></MemoryRouter></StrictMode>);
    expect(screen.getByRole("complementary", { name: "Built by makers" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss maker mode" }));
    expect(window.sessionStorage.getItem("sw.delight.maker-pending")).toBeNull();
  });

  it("forgets clicks older than four seconds", () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    motion(false);
    window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: true };
    const { container } = shell("/m/forge");
    const logo = container.querySelector("[data-logo]")!;
    for (let click = 0; click < 6; click += 1) fireEvent.click(logo);
    vi.setSystemTime(Date.now() + 4100);
    fireEvent.click(logo);
    expect(screen.queryByRole("complementary", { name: "Built by makers" })).toBeNull();
  });

  it("still works on one page when sessionStorage is blocked", () => {
    motion(false);
    window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: true };
    const blocked = () => { throw new Error("blocked"); };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(blocked);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(blocked);
    const { container } = shell("/m/forge");
    for (let click = 0; click < 7; click += 1) fireEvent.click(container.querySelector("[data-logo]")!);
    expect(screen.getByRole("complementary", { name: "Built by makers" })).toBeInTheDocument();
  });
});

describe("return confetti", () => {
  it("bursts once, decoratively, then goes away", () => {
    motion(false);
    vi.useFakeTimers();
    const { container } = render(delight(<ReturnConfetti />));
    const burst = container.querySelector(".sw-confetti-anchor")!;
    expect(burst).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelectorAll(".sw-confetti-piece")).toHaveLength(16);
    expect(container.querySelector(".sw-confetti-box")).not.toBeNull();
    expect(container.querySelector(".sw-confetti-circle")).not.toBeNull();
    expect(container.textContent).toBe("");
    act(() => { vi.advanceTimersByTime(1300); });
    expect(container.querySelector(".sw-confetti-piece")).toBeNull();
  });

  it("keeps to teal, orange, sky blue and the panel's ink on a citron or yellow panel", () => {
    motion(false);
    const colours = (container: HTMLElement) => new Set([...container.querySelectorAll<HTMLElement>(".sw-confetti-piece")].map(piece => piece.style.getPropertyValue("--piece")));
    for (const tone of ["success", "warn"] as const) {
      const { container, unmount } = render(delight(<ResultPanel tone={tone} title="Return recorded" summary={<ReturnConfetti />} next={{ label: "Done", onClick() {} }} />));
      expect([...colours(container)].sort()).toEqual(["--color-accent", "--color-emphasis", "--color-info", `--color-on-${tone}`].map(token => `rgb(var(${token}))`).sort());
      unmount();
    }
    const plain = render(delight(<ReturnConfetti />)).container;
    expect(colours(plain)).toContain("rgb(var(--color-success))");
    expect(confettiPalette("danger")).toContain("--color-warn");
  });

  it("stays away under reduced motion, with delight off, and on checkout or kiosk paths", () => {
    motion(true);
    expect(render(delight(<ReturnConfetti />)).container.innerHTML).toBe("");
    motion(false);
    expect(render(<DelightProvider enabled={false}><ReturnConfetti /></DelightProvider>).container.innerHTML).toBe("");
    for (const path of ["/m/forge/checkout", "/kiosk/abc", "/m/forge/payments"]) {
      at(path);
      expect(render(delight(<ReturnConfetti />)).container.innerHTML).toBe("");
    }
  });
});

describe("sneaky lines", () => {
  it("answers sudo make in a search box with one Okay toast a session", () => {
    render(<><SudoMake allowed /><input type="search" aria-label="Search" /><input aria-label="Name" /></>);
    const search = screen.getByRole("searchbox");
    const okays = () => toastStore.snapshot().filter(row => row.message === "Okay.").length;
    fireEvent.input(screen.getByLabelText("Name"), { target: { value: "sudo make" } });
    expect(okays()).toBe(0);
    fireEvent.input(search, { target: { value: "sudo make" } });
    expect(okays()).toBe(1);
    fireEvent.input(search, { target: { value: "" } });
    fireEvent.input(search, { target: { value: "sudo make" } });
    expect(okays()).toBe(1);
  });

  it("does nothing when eggs are not allowed", () => {
    window.sessionStorage.clear();
    render(<><SudoMake allowed={false} /><input type="search" aria-label="Search" /></>);
    const before = toastStore.snapshot().length;
    fireEvent.input(screen.getByRole("searchbox"), { target: { value: "sudo make" } });
    expect(toastStore.snapshot().length).toBe(before);
  });

  it("shows a visible late-shift line from midnight to 4 am only, with a keyboard dismiss kept for the session", () => {
    const night = new Date(2026, 9, 20, 1, 30);
    const { container, rerender, unmount } = render(delight(<LateShiftLine now={night} />));
    const line = screen.getByText("Late shift? The solder's still warm.").parentElement!;
    expect(line.closest("[aria-hidden]")).toBeNull();
    expect(line).toHaveClass("text-muted");
    const dismiss = screen.getByRole("button", { name: "Dismiss" });
    expect(dismiss).not.toHaveAttribute("tabindex");
    expect(dismiss.className).toContain("focus-visible:outline-focus");
    rerender(delight(<LateShiftLine now={new Date(2026, 9, 20, 4, 0)} />));
    expect(container.innerHTML).toBe("");
    rerender(delight(<LateShiftLine now={night} />, false));
    expect(container.innerHTML).toBe("");
    rerender(delight(<LateShiftLine now={night} />));
    dismiss.focus();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(container.innerHTML).toBe("");
    unmount();
    expect(render(delight(<LateShiftLine now={night} />)).container.innerHTML).toBe("");
    expect(window.sessionStorage.getItem("sw.delight.late-shift")).toBe("1");
  });

  it("never shows on kiosk paths", () => {
    at("/m/forge/kiosk/abc");
    expect(render(delight(<LateShiftLine now={new Date(2026, 9, 20, 2, 0)} />)).container.innerHTML).toBe("");
  });
});

describe("first-load stagger", () => {
  it("staggers on first mount only, then drops the class", () => {
    motion(false);
    vi.useFakeTimers();
    const { container } = render(delight(<StaggerGroup className="grid"><p>a</p><p>b</p></StaggerGroup>));
    expect(container.firstElementChild).toHaveClass("grid", "sw-stagger");
    act(() => { vi.advanceTimersByTime(600); });
    expect(container.firstElementChild).not.toHaveClass("sw-stagger");
    expect(container.firstElementChild).toHaveClass("grid");
  });

  it("is off under reduced motion, with delight off and on kiosk paths", () => {
    motion(true);
    expect(render(delight(<StaggerGroup><p>a</p></StaggerGroup>)).container.firstElementChild).not.toHaveClass("sw-stagger");
    motion(false);
    expect(render(<DelightProvider enabled={false}><StaggerGroup><p>a</p></StaggerGroup></DelightProvider>).container.firstElementChild).not.toHaveClass("sw-stagger");
    at("/kiosk/abc");
    expect(render(delight(<StaggerGroup><p>a</p></StaggerGroup>)).container.firstElementChild).not.toHaveClass("sw-stagger");
  });
});
