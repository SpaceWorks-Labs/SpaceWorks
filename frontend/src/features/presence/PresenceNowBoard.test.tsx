import type { ReactNode } from "react";
import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { PresenceNowBoard, TV_REFRESH_MS } from "./PresenceNowBoard";

const api = vi.hoisted(() => ({ tenantPublicRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), tenantPublicRequest: api.tenantPublicRequest }));

const since = new Date(Date.now() - 45 * 60_000).toISOString();
const rows = [
  { display_name: "Asha Rao", status: "working", project_title: "CNC clock", since },
  { display_name: "A member", status: "visiting", since },
  { display_name: "A guest", status: "guest", since },
  { display_name: "Ravi K", status: "attending_event", event_title: "Solder night", since },
];
const wrap = (ui: ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
const renderBoard = (enabled = true) => render(wrap(<PresenceNowBoard slug="lab" spaceName="Lab" enabled={enabled} />));

beforeEach(() => { api.tenantPublicRequest.mockReset(); api.tenantPublicRequest.mockResolvedValue(rows); });
afterEach(() => { vi.useRealTimers(); focusManager.setFocused(undefined); });

describe("PresenceNowBoard", () => {
  it("reads the anonymous TV endpoint and renders large privacy-safe rows", async () => {
    renderBoard();
    const list = await screen.findByRole("list", { name: "People here now" });
    expect(api.tenantPublicRequest).toHaveBeenCalledWith("lab", "/public/makerspaces/lab/presence/now/");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items[0]).toHaveTextContent("Asha Rao");
    expect(items[0]).toHaveTextContent("Working on a project · CNC clock");
    expect(items[1]).toHaveTextContent("A member");
    expect(items[1]).toHaveTextContent("Visiting");
    expect(items[2]).toHaveTextContent("A guest");
    expect(items[3]).toHaveTextContent("Attending an event · Solder night");
    expect(items[0]).toHaveTextContent(/Here since/);
    expect(screen.getByRole("heading", { name: "Who's in at Lab" })).toBeInTheDocument();
  });

  it("renders only the projected fields, never an unexpected identifier or contact", async () => {
    api.tenantPublicRequest.mockResolvedValue([{ ...rows[1], account_id: 991, email: "leak@example.com", project_title: "Hidden" }]);
    renderBoard();
    const item = within(await screen.findByRole("list", { name: "People here now" })).getByRole("listitem");
    expect(item).not.toHaveTextContent("991");
    expect(item).not.toHaveTextContent("leak@example.com");
    // A project title only belongs to a "working" row.
    expect(item).not.toHaveTextContent("Hidden");
  });

  it("shows an empty state when no one is in", async () => {
    api.tenantPublicRequest.mockResolvedValue([]);
    renderBoard();
    expect(await screen.findByText("No one is checked in right now.")).toBeInTheDocument();
  });

  it("sends no request and says the display is unavailable when the module is off", () => {
    renderBoard(false);
    expect(screen.getByText("This display isn't available for this makerspace.")).toBeInTheDocument();
    expect(api.tenantPublicRequest).not.toHaveBeenCalled();
  });

  it("treats a 404 (module off server-side) as unavailable", async () => {
    api.tenantPublicRequest.mockRejectedValue(new StructuredApiError(404, {}));
    renderBoard();
    expect(await screen.findByText("This display isn't available for this makerspace.")).toBeInTheDocument();
  });

  it("refreshes every 30 seconds while visible and pauses while hidden", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    expect(TV_REFRESH_MS).toBe(30_000);
    renderBoard();
    await screen.findByRole("list", { name: "People here now" });
    expect(api.tenantPublicRequest).toHaveBeenCalledTimes(1);
    await act(() => vi.advanceTimersByTimeAsync(TV_REFRESH_MS));
    expect(api.tenantPublicRequest).toHaveBeenCalledTimes(2);
    act(() => focusManager.setFocused(false));
    await act(() => vi.advanceTimersByTimeAsync(TV_REFRESH_MS * 3));
    expect(api.tenantPublicRequest).toHaveBeenCalledTimes(2);
  });

  it("keeps the last rows and flags offline when a refresh fails", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    renderBoard();
    await screen.findByRole("list", { name: "People here now" });
    api.tenantPublicRequest.mockRejectedValue(new Error("network"));
    await act(() => vi.advanceTimersByTimeAsync(TV_REFRESH_MS));
    expect(screen.getByRole("list", { name: "People here now" })).toBeInTheDocument();
    expect(await screen.findByText("Offline")).toBeInTheDocument();
  });
});
