import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { replayRoute } from "../../lib/telemetry/replayRoutes";
import { safePage } from "../../lib/telemetry/policy";
import { analyticsTemplate, isBearerUrl } from "../../lib/webAnalytics";
import { displayScreenApi, type AdminDisplay, type DisplayState } from "./api";
import { DisplayCanvas } from "./DisplayCanvas";
import { PanelOrderEditor, moveItem } from "./PanelOrderEditor";
import { previewHereNow, sampleState } from "./previewState";
import { ScreenLinkBlock, suggestedSeconds } from "./ScreenLinkBlock";
import { SpaceDisplayPage } from "./SpaceDisplayPage";
import { linkToken, POLL_PAIRED_MS } from "./useDisplayScreen";

type Paired = Extract<DisplayState, { state: "paired" }>;
const flush = async () => { await act(async () => { if (vi.isFakeTimers()) { for (let i = 0; i < 4; i += 1) await vi.advanceTimersByTimeAsync(5); } else { await Promise.resolve(); await Promise.resolve(); } }); };
const renderPage = () => render(<QueryClientProvider client={new QueryClient()}><SpaceDisplayPage /></QueryClientProvider>);

describe("display routes stay private", () => {
  const at = (path: string) => new URL(path, window.location.origin);
  it("never feeds analytics, replay or the consent banner, with or without the link fragment", () => {
    for (const path of ["/display", "/display#k=abc", "/stats/tv"]) {
      expect(analyticsTemplate(at(path))).toBeNull();
      expect(safePage(at(path))).toBeNull();
    }
    expect(isBearerUrl(at("/display#k=abc"))).toBe(true);
    expect(replayRoute("posthog", analyticsTemplate(at("/display")))).toBe(false);
    expect(replayRoute("clarity", "/display")).toBe(false);
  });
});

describe("screen link address", () => {
  beforeEach(() => { vi.useFakeTimers(); window.localStorage.clear(); window.location.hash = "#k=fromlink"; });
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); window.location.hash = ""; });
  it("reads the secret from the fragment and never registers a new screen", async () => {
    const register = vi.spyOn(displayScreenApi, "register");
    const state = vi.spyOn(displayScreenApi, "state").mockResolvedValue(sampleState({ panels: ["announcement"], layout: "single" }, "Lab"));
    expect(linkToken()).toBe("fromlink");
    renderPage();
    await flush();
    expect(state.mock.calls[0][0]).toBe("fromlink");
    expect(register).not.toHaveBeenCalled();
    expect(window.localStorage.getItem("sw-space-display-token")).toBeNull();
  });
  it("says so, instead of showing a code, when the address was revoked", async () => {
    const { DisplayHttpError } = await import("./api");
    vi.spyOn(displayScreenApi, "state").mockRejectedValue(new DisplayHttpError(404));
    const register = vi.spyOn(displayScreenApi, "register");
    renderPage();
    await flush();
    expect(screen.getByText(/no longer valid/i)).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
  });
  it("polls on the screen's own refresh interval", async () => {
    const state = vi.spyOn(displayScreenApi, "state").mockResolvedValue({ ...sampleState({ panels: ["announcement"], refresh_seconds: 20 }, "Lab") });
    renderPage();
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_PAIRED_MS + 100); });
    expect(state).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(state).toHaveBeenCalledTimes(2);
  });
});

describe("layouts and themes", () => {
  const now = Date.now();
  it("grid shows every section at once, single only the first", () => {
    const base = sampleState({ panels: ["announcement", "opening_hours", "public_stats"], announcement: "Open day" }, "Lab");
    const { unmount } = render(<DisplayCanvas state={{ ...base, config: { ...base.config, layout: "grid" } }} now={now} />);
    expect(screen.getByText("Open day")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Opening hours" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /In numbers/ })).toBeInTheDocument();
    unmount();
    render(<DisplayCanvas state={{ ...base, config: { ...base.config, layout: "single" } }} now={now} />);
    expect(screen.getByText("Open day")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Opening hours" })).toBeNull();
  });
  it("playlist advances after the slide's own seconds", async () => {
    vi.useFakeTimers();
    const base = sampleState({ panels: ["announcement", "opening_hours"], announcement: "Open day", slide_seconds: { announcement: 7 } }, "Lab");
    render(<DisplayCanvas state={base} now={now} />);
    expect(screen.getByText("Open day")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(7_100); });
    expect(screen.getByRole("heading", { name: "Opening hours" })).toBeInTheDocument();
    vi.useRealTimers();
  });
  it("themes: solid black and light pick their surfaces", async () => {
    vi.useFakeTimers();
    vi.spyOn(displayScreenApi, "state").mockResolvedValue(sampleState({ panels: ["announcement"], theme: "black" }, "Lab"));
    window.localStorage.setItem("sw-space-display-token", "t");
    const { container } = renderPage();
    await flush();
    expect(container.querySelector("main")?.className).toContain("bg-black");
    vi.useRealTimers();
  });
});

describe("privacy preview only narrows", () => {
  it("first names and counts hide handles, avatars and skills", () => {
    expect(previewHereNow("profiles").people[0].display_name).toBe("Asha Verma");
    const first = previewHereNow("first_names");
    expect(first.people.map((p) => p.display_name)).toEqual(["Asha", "Tomas"]);
    expect(first.people.every((p) => p.handle === null && p.skills.length === 0)).toBe(true);
    expect(previewHereNow("counts")).toMatchObject({ people: [], others_count: 6, total: 6 });
  });
});

describe("panel order editor", () => {
  it("moveItem is pure and bounds-safe", () => {
    expect(moveItem(["a", "b", "c"], 0, 2)).toEqual(["b", "c", "a"]);
    const same = ["a", "b"];
    expect(moveItem(same, 0, 5)).toBe(same);
  });
  it("reorders with the keyboard-reachable buttons and adds a section from the unchecked list", () => {
    const onChange = vi.fn();
    render(<PanelOrderEditor legend="Sections" all={["a", "b", "c"]} value={["a", "b"]} label={(k) => k.toUpperCase()} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Move A down" }));
    expect(onChange).toHaveBeenLastCalledWith(["b", "a"]);
    expect(screen.getByRole("button", { name: "Move A up" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "C" }));
    expect(onChange).toHaveBeenLastCalledWith(["a", "b", "c"]);
  });
});

describe("Use with Anthias block", () => {
  const row: AdminDisplay = { id: 1, name: "Lobby", panels: ["here_now", "calendar"], rotation_seconds: 15, announcement: "", claimed_at: "", last_seen_at: null,
    online: true, layout: "playlist", theme: "dark", privacy: "profiles", refresh_seconds: 30, slide_seconds: { here_now: 20 }, player_ids: [],
    has_link: true, url: "" };
  const issued = "https://spaces.example/display#k=secret";
  it("suggests a full playlist pass and shows the address just issued", () => {
    expect(suggestedSeconds({ ...row, panels: ["here_now", "calendar"], slide_seconds: { here_now: 20 } })).toBe(35);
    expect(suggestedSeconds({ ...row, layout: "grid" })).toBe(60);
    render(<ScreenLinkBlock row={row} url={issued} busy={false} onRotate={() => undefined} />);
    expect(screen.getByLabelText("Screen address")).toHaveValue(issued);
    expect(screen.getByText(/Suggested duration: 35 seconds/)).toBeInTheDocument();
  });
  it("never re-shows an address the server no longer returns: it offers a new one instead", () => {
    render(<ScreenLinkBlock row={row} url="" busy={false} onRotate={() => undefined} />);
    expect(screen.queryByLabelText("Screen address")).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy address" })).toBeNull();
    expect(screen.getByText(/shown only when it is made/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New address" })).toBeInTheDocument();
  });
});

describe("paired state type", () => {
  it("sample state is a valid paired screen", () => { const s: Paired = sampleState({}, "Lab"); expect(s.state).toBe("paired"); });
});
