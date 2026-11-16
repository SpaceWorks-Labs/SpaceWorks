import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DisplayHttpError, displayScreenApi, type DisplayState } from "./api";
import { SpaceDisplayPage } from "./SpaceDisplayPage";
import { availablePanels, POLL_PAIRED_MS, RETRY_MS, TOKEN_KEY } from "./useDisplayScreen";

const paired = (over: Partial<Extract<DisplayState, { state: "paired" }>> = {}): DisplayState => ({
  state: "paired", generated_at: new Date().toISOString(), space: { name: "Lab", slug: "lab", timezone: "UTC" },
  config: { name: "Lobby", panels: ["here_now", "machines", "announcement"], rotation_seconds: 15, version: 1,
    layout: "playlist", theme: "dark", privacy: "profiles", refresh_seconds: 10, slide_seconds: {} },
  here_now: { audience: "public", total: 2, others_count: 2, people: [] },
  calendar: null, machines: null, announcement: null, public_stats: null, opening_hours: null, ...over });

/** TanStack batches renders on a 0 ms timer, so flushing advances fake time a little as well. */
const flush = async () => { for (let i = 0; i < 4; i += 1) await act(async () => { await vi.advanceTimersByTimeAsync(5); }); };

function renderDisplay(strict = false) {
  const client = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
  const page = <QueryClientProvider client={client}><SpaceDisplayPage /></QueryClientProvider>;
  return render(strict ? <StrictMode>{page}</StrictMode> : page);
}

beforeEach(() => { vi.useFakeTimers(); window.localStorage.clear(); });
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("SpaceDisplayPage", () => {
  it("registers, shows the pairing code and keeps the secret for the next load", async () => {
    vi.spyOn(displayScreenApi, "register").mockResolvedValue({ token: "secret", code: "K7M2QX", code_expires_at: "2026-11-11T12:00:00Z" });
    vi.spyOn(displayScreenApi, "state").mockResolvedValue({ state: "unclaimed", code: "K7M2QX", code_expires_at: "2026-11-11T12:00:00Z" });
    renderDisplay();
    await flush();
    expect(screen.getByLabelText("Pairing code")).toHaveTextContent("K7M2QX");
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("secret");
  });

  it("registers once even when StrictMode mounts the page twice", async () => {
    const register = vi.spyOn(displayScreenApi, "register").mockResolvedValue({ token: "secret", code: "K7M2QX", code_expires_at: "" });
    vi.spyOn(displayScreenApi, "state").mockResolvedValue({ state: "unclaimed", code: "K7M2QX", code_expires_at: "" });
    renderDisplay(true);
    await flush();
    expect(register).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Pairing code")).toHaveTextContent("K7M2QX");
  });

  it("polls with the secret as an argument (header), never building a path from it", async () => {
    window.localStorage.setItem(TOKEN_KEY, "secret");
    const state = vi.spyOn(displayScreenApi, "state").mockResolvedValue(paired());
    renderDisplay();
    await flush();
    expect(state.mock.calls[0][0]).toBe("secret");
    expect(state.mock.calls[0][1]).toBeInstanceOf(AbortSignal);
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_PAIRED_MS + 10); });
    expect(state).toHaveBeenCalledTimes(2);
  });

  it("shows the paired panel for the space, only the count when nobody is named", async () => {
    window.localStorage.setItem(TOKEN_KEY, "secret");
    vi.spyOn(displayScreenApi, "state").mockResolvedValue(paired());
    renderDisplay();
    await flush();
    expect(screen.getByText("Lab")).toBeInTheDocument();
    expect(screen.getByText("2 here now")).toBeInTheDocument();
  });

  it("keeps the last data and says it is reconnecting when the network fails", async () => {
    window.localStorage.setItem(TOKEN_KEY, "secret");
    const state = vi.spyOn(displayScreenApi, "state").mockResolvedValueOnce(paired());
    renderDisplay();
    await flush();
    state.mockRejectedValue(new TypeError("offline"));
    await act(async () => { await vi.advanceTimersByTimeAsync(POLL_PAIRED_MS + 10); });
    expect(screen.getByRole("status")).toHaveTextContent("Reconnecting…");
    expect(screen.getByText("2 here now")).toBeInTheDocument();
  });

  it("drops the secret and asks for a new code when the server no longer knows the screen", async () => {
    window.localStorage.setItem(TOKEN_KEY, "revoked");
    vi.spyOn(displayScreenApi, "state").mockRejectedValue(new DisplayHttpError(404));
    const register = vi.spyOn(displayScreenApi, "register").mockResolvedValue({ token: "fresh", code: "NEW234", code_expires_at: "" });
    renderDisplay();
    await flush();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(screen.getByText("Getting a new pairing code…")).toBeInTheDocument();
    expect(register).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(RETRY_MS + 10); });
    expect(register).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(TOKEN_KEY)).toBe("fresh");
  });
});

describe("displayScreenApi", () => {
  it("sends the secret in the Authorization header to the fixed path, without cookies or referrer", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ state: "unclaimed", code: "A", code_expires_at: "" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    try {
      await displayScreenApi.state("s3cr3t-token");
      const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url.endsWith("/space-displays/state/")).toBe(true);
      expect(url).not.toContain("s3cr3t-token");
      expect((init.headers as Record<string, string>).Authorization).toBe("Display s3cr3t-token");
      expect(init.credentials).toBe("omit");
      expect(init.referrerPolicy).toBe("no-referrer");
    } finally { vi.unstubAllGlobals(); }
  });

  it("maps a 404 to DisplayHttpError so the screen re-pairs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 404 })));
    try { await expect(displayScreenApi.state("gone")).rejects.toMatchObject({ status: 404 }); } finally { vi.unstubAllGlobals(); }
  });
});

describe("availablePanels", () => {
  it("keeps staff order and drops panels with nothing to show", () => {
    const state = paired({ announcement: "Open day", machines: { in_use: 0, free: 0, out_of_service: 0, items: [] } });
    expect(availablePanels(state)).toEqual(["here_now", "announcement"]);
    expect(availablePanels({ state: "unclaimed", code: "A", code_expires_at: "" })).toEqual([]);
  });
});
