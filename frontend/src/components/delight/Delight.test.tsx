import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DelightProvider, eggsAllowed } from "./DelightProvider";
import { PassState } from "./PassState";
import { DotMeter, EventTimeChip, SetupChecklist } from "./StatusDetails";
import { SpaceWorksDemo } from "../../features/landing/SpaceWorksDemo";
import { MakerModePanel, MakerModeToggle, useMakerMode } from "./EasterEggs";
import { WorkshopLogbook } from "./WorkshopLogbook";
import { DelightFixtures } from "./DelightFixtures";
import { doorSoundsEnabled, playDoorSound, setDoorSounds } from "./doorSounds";
import { WordFeedback } from "./WordFeedback";
import { revealTheme } from "./themeReveal";
import { expectNoA11yViolations } from "../../test/axe";
import { SuccessCard } from "./SuccessCard";

function EggHarness({ path = "/about" }: { path?: string }) {
  const mode = useMakerMode(path);
  return <><input aria-label="Editor" /><button type="button" onClick={mode.activateLogo}>Logo</button><MakerModeToggle mode={mode} /><MakerModePanel mode={mode} version="1.2.3" /></>;
}
const konami = () => ["ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight", "b", "a"].forEach(key => fireEvent.keyDown(window, { key }));

beforeEach(() => {
  window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: true };
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  localStorage.clear();
});
afterEach(() => { delete window.__TENANT__; cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("persisted pass state", () => {
  it("survives remount, never repeats haptics for polling or initial load", () => {
    const vibrate = vi.fn(); vi.stubGlobal("navigator", { vibrate });
    const value = { state: "completed" as const, label: "Returned", completedAt: "2026-10-18T10:00:00Z" };
    const result = render(<PassState title="Loan" value={value} haptics />);
    expect(screen.getByText("Returned")).toBeTruthy();
    result.rerender(<PassState title="Loan" value={{ ...value }} haptics />);
    expect(vibrate).not.toHaveBeenCalled();
    expect(result.container.querySelector(".sw-delight-pass")).toBeNull();
    result.unmount(); render(<PassState title="Loan" value={value} />);
    expect(screen.getByText("Returned")).toBeTruthy();
  });
  it("preserves state with delight disabled", () => {
    render(<DelightProvider enabled={false}><PassState title="Loan" value={{ state: "ready", label: "Awaiting handover" }} /></DelightProvider>);
    expect(screen.getByText("Awaiting handover")).toBeTruthy();
  });
});

it("does not expose hidden or status-only counts as dots", () => {
  const result = render(<DotMeter value={{ mode: "hidden" }} />);
  expect(result.container.textContent).toBe("");
  result.rerender(<DotMeter value={{ mode: "status_only", label: "Limited" }} />);
  expect(screen.getByText("Limited")).toBeTruthy();
  expect(result.container.querySelector('[aria-hidden="true"]')).toBeNull();
  result.rerender(<DotMeter value={{ mode: "exact_count", count: 2, total: 10 }} />);
  expect(screen.getByText("2 of 10 available")).toBeTruthy();
});

it("uses explicit time and hides unavailable setup actions", () => {
  render(<><EventTimeChip startsAt="2026-10-18T10:00:00Z" endsAt="2026-10-18T12:00:00Z" now={new Date("2026-10-18T11:00:00Z")} />
    <SetupChecklist steps={[{ key: "staff", label: "Staff", done: false, available: false, href: "/staff" }]} /></>);
  expect(screen.getByText("Happening now")).toBeTruthy(); expect(screen.queryByText("Staff")).toBeNull();
});

it("demo and logbook are local button interactions and can be disabled", () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const result = render(<><SpaceWorksDemo /><WorkshopLogbook /></>);
  fireEvent.click(screen.getByRole("button", { name: "Scan sample box" }));
  expect(screen.getByText("Sample box: Issued")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reset demo" }));
  expect(screen.getByText("Sample box: On shelf")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Open the workshop logbook" }));
  expect(screen.getByRole("article")).toBeTruthy();
  expect(fetch).not.toHaveBeenCalled();
  result.rerender(<DelightProvider enabled={false}><SpaceWorksDemo /><WorkshopLogbook /></DelightProvider>);
  expect(result.container.textContent).toBe("");
});

it("word schema leaves historical numeric ratings unchanged", () => {
  const change = vi.fn();
  const result = render(<WordFeedback version="legacy_numeric" value={4} onChange={change} />);
  expect(screen.getByText("Recorded rating: 4")).toBeTruthy();
  result.rerender(<WordFeedback version="words_v1" value={null} onChange={change} />);
  fireEvent.click(screen.getByRole("radio", { name: "Good" })); expect(change).toHaveBeenCalledWith("good");
});

describe("client-only eggs", () => {
  it("supports normal toggle, sequence, dismissal and expiration without network", () => {
    vi.useFakeTimers(); const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const storage = vi.spyOn(Storage.prototype, "setItem");
    render(<EggHarness />); fireEvent.click(screen.getByRole("button", { name: "Maker mode: off" }));
    expect(screen.getByRole("button", { name: "Maker mode: on" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss maker mode" }));
    konami(); expect(screen.getByRole("button", { name: "Maker mode: on" })).toBeTruthy();
    act(() => vi.advanceTimersByTime(12000)); expect(screen.getByRole("button", { name: "Maker mode: off" })).toBeTruthy();
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByRole("button", { name: "Logo" }));
    expect(screen.getByText("Space Works 1.2.3")).toBeTruthy(); expect(fetch).not.toHaveBeenCalled();
    // The logo count survives a logo link's page load, so it writes only its own sessionStorage keys.
    expect(storage.mock.contexts.every(target => target === window.sessionStorage)).toBe(true);
    expect(storage.mock.calls.every(([key]) => key.startsWith("sw.delight."))).toBe(true);
  });
  it("ignores editor keys and completely disables itself on sensitive routes and flag off", () => {
    const result = render(<EggHarness />);
    const editor = screen.getByRole("textbox");
    ["ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight", "b", "a"].forEach(key => fireEvent.keyDown(editor, { key }));
    expect(screen.queryByRole("button", { name: "Maker mode: on" })).toBeNull();
    for (const path of ["/kiosk", "/admin/scanner", "/events/x/check-in", "/payments/checkout", "/m/x/checkin", "/events/x?tab=checkin"]) expect(eggsAllowed(path)).toBe(false);
    result.rerender(<EggHarness path="/payments/checkout" />); konami();
    expect(screen.queryByText("Built by makers")).toBeNull(); expect(screen.queryByRole("button", { name: "Maker mode: off" })).toBeNull();
    result.rerender(<DelightProvider eggsEnabled={false}><EggHarness /></DelightProvider>); konami();
    expect(screen.queryByRole("button", { name: "Maker mode: off" })).toBeNull();
  });
});

it("sounds default off, require user activation and tolerate missing audio", async () => {
  const Audio = vi.fn(); vi.stubGlobal("AudioContext", Audio);
  expect(doorSoundsEnabled()).toBe(false); await playDoorSound("success"); expect(Audio).not.toHaveBeenCalled();
  setDoorSounds(true); await playDoorSound("success"); expect(Audio).not.toHaveBeenCalled();
});

it("enables result playback only after explicit sound preference and hides controls flag-off", () => {
  const result = render(<SuccessCard kind="success" name="Alex" message="Checked in." resultId="recorded" />);
  expect(screen.getByRole("button", { name: "Play result sound" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Door sounds: off" }));
  expect(screen.getByRole("button", { name: "Play result sound" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Door sounds: on" })).toHaveAttribute("aria-pressed", "true");
  result.rerender(<DelightProvider enabled={false}><SuccessCard kind="success" name="Alex" message="Checked in." resultId="recorded" /></DelightProvider>);
  expect(screen.queryByRole("button", { name: "Play result sound" })).toBeNull();
  expect(screen.getByText("Checked in.")).toBeTruthy();
});

it("theme reduced-motion and flag-off paths apply instantly", () => {
  const transition = vi.fn(); Object.defineProperty(document, "startViewTransition", { configurable: true, value: transition });
  revealTheme("dark", document.body, true, true); expect(document.documentElement.classList.contains("dark")).toBe(true);
  revealTheme("light", document.body, false, false); expect(document.documentElement.classList.contains("dark")).toBe(false);
  expect(transition).not.toHaveBeenCalled();
});

it("exposes all twelve pack rows for browser light/dark/a11y acceptance", () => {
  render(<DelightFixtures />);
  for (const name of ["1 Persistent pass", "2 Result card", "3 Loader and moods", "4 Companion", "5 Theme reveal", "6 Greetings and setup", "7 Meters and time", "8 Word feedback", "9 Logbook", "10 Landing demo", "11 Plain errors", "12 Maker mode"]) {
    expect(screen.getByRole("region", { name })).toBeTruthy();
  }
});

it("keeps all pack fixtures accessible with reduced motion", async () => {
  const result = render(<DelightFixtures />);
  expect(result.container.querySelector(".sw-delight-result")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Open the workshop logbook" }));
  fireEvent.click(screen.getByRole("button", { name: "Workshop companion: off" }));
  fireEvent.click(screen.getByRole("button", { name: "Print a tiny layer stack" }));
  expect(result.container.querySelector(".sw-delight-logbook")).toBeNull();
  await expectNoA11yViolations(result.container);
});

it("falls back from unavailable transitions without changing theme choice", () => {
  // Motion allowed for this case (the suite's default stub reports reduced motion).
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  const animation = vi.fn();
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: undefined });
  Object.defineProperty(document.documentElement, "animate", { configurable: true, value: animation });
  revealTheme("dark", document.body, true, false);
  expect(document.documentElement.classList.contains("dark")).toBe(true);
  // Without View Transitions every colour cross-fades through a temporary class.
  expect(document.documentElement.classList.contains("sw-theme-fade")).toBe(true);
  expect(animation).not.toHaveBeenCalled();
  Object.defineProperty(document, "startViewTransition", { configurable: true, value: () => { throw new Error("unsupported"); } });
  revealTheme("light", document.body, true, false);
  expect(document.documentElement.classList.contains("dark")).toBe(false);
});
