import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { PresenceCheckInSheet, type PresenceCheckInSheetProps } from "./PresenceCheckInSheet";

const api = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), memberRequest: api.memberRequest }));

type Coords = { latitude: number; longitude: number; accuracy: number };
function mockGeolocation(result: { ok: Coords } | { code: 1 | 2 | 3 } | null, permission = "prompt") {
  const getCurrentPosition = (ok: (p: { coords: Coords }) => void, fail: (e: { code: number }) => void) => {
    if (result && "ok" in result) ok({ coords: result.ok }); else if (result) fail({ code: result.code });
  };
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: result === null ? undefined : { getCurrentPosition } });
  Object.defineProperty(navigator, "permissions", { configurable: true, value: { query: async () => ({ state: permission }) } });
}
const wrap = (ui: ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
const inside = { ok: { latitude: 12.97, longitude: 77.59, accuracy: 12 } };
const projects = { count: 2, next: null, previous: null, results: [{ id: 7, title: "CNC clock", public_visible: true }, { id: 8, title: "Secret robot", public_visible: false }] };

function respond(overrides: Record<string, unknown> = {}) {
  api.memberRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.endsWith("/projects")) return overrides.projects ?? projects;
    if (path.endsWith("/preferences")) return { hide_on_display: false };
    if (options?.method === "POST") {
      if (overrides.startError) throw overrides.startError;
      return { active: true, status: "visiting", expires_at: new Date(Date.now() + 3_600_000).toISOString() };
    }
    throw new Error(`unexpected ${path}`);
  });
}
const startCalls = () => api.memberRequest.mock.calls.filter(([, options]) => (options as RequestInit | undefined)?.method === "POST");
const startBody = () => JSON.parse(String((startCalls()[0][1] as RequestInit).body));

function renderSheet(props: Partial<PresenceCheckInSheetProps> = {}) {
  const onClose = vi.fn();
  render(wrap(<PresenceCheckInSheet slug="lab" open onClose={onClose} presets={[60, 120, 180, 240]} member selfCheckIn optOutAllowed {...props} />));
  return { onClose };
}

beforeEach(() => { api.memberRequest.mockReset(); respond(); mockGeolocation(inside); });
afterEach(() => vi.restoreAllMocks());

describe("PresenceCheckInSheet", () => {
  it("offers the 1/2/3/4 hour presets and sends the chosen one with the location reading", async () => {
    const { onClose } = renderSheet();
    const group = screen.getByRole("radiogroup", { name: "How long are you staying?" });
    expect(["1 h", "2 h", "3 h", "4 h"].map((label) => screen.getByRole("radio", { name: label }))).toHaveLength(4);
    expect(group).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "2 h" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: "3 h" }));
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(startCalls()[0][0]).toBe("/public/lab/presence-sessions");
    expect(startBody()).toEqual({ duration_minutes: 180, latitude: 12.97, longitude: 77.59, accuracy: 12, status: "visiting", hide_on_display: false });
  });

  it("requires one of the member's own projects for Working and marks private ones", async () => {
    renderSheet();
    fireEvent.click(screen.getByRole("radio", { name: "Working on a project" }));
    const select = await screen.findByRole("combobox", { name: "Which project?" });
    expect(screen.getByRole("option", { name: "Secret robot (private)" })).toBeInTheDocument();
    expect(screen.getByText("Private projects are never named on the display.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check in" })).toBeDisabled();
    fireEvent.change(select, { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(startCalls()).toHaveLength(1));
    expect(startBody()).toMatchObject({ status: "working", project_id: 8 });
  });

  it("explains how to proceed when the member has no projects", async () => {
    respond({ projects: { count: 0, next: null, previous: null, results: [] } });
    renderSheet();
    fireEvent.click(screen.getByRole("radio", { name: "Working on a project" }));
    expect(await screen.findByText(/no projects on your profile yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check in" })).toBeDisabled();
  });

  it("checks a non-member in as a guest without a status picker", async () => {
    const { onClose } = renderSheet({ member: false });
    expect(screen.queryByRole("radiogroup", { name: "What are you here for?" })).not.toBeInTheDocument();
    expect(screen.getByText("guest")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(startBody()).toMatchObject({ status: "guest" });
    expect(api.memberRequest.mock.calls.some(([path]) => String(path).endsWith("/projects"))).toBe(false);
  });

  it.each([
    [{ code: 1 as const }, /Location access is blocked/],
    [{ code: 2 as const }, /couldn't find your location/],
    [{ code: 3 as const }, /took too long/],
    [null, /can't share a location/],
  ])("refuses without a reading (%o) and points to staff check-in", async (result, message) => {
    mockGeolocation(result);
    renderSheet();
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    expect(alert).toHaveTextContent("Ask staff at the desk or use the check-in kiosk instead.");
    expect(startCalls()).toHaveLength(0);
  });

  it("warns up front when location permission is already denied", async () => {
    mockGeolocation(inside, "denied");
    renderSheet();
    expect(await screen.findByRole("alert")).toHaveTextContent(/Location access is blocked/);
  });

  it("shows the server's outside-the-area refusal with the staff alternative", async () => {
    respond({ startError: new StructuredApiError(400, { code: "outside_geofence", detail: "Location must be inside the makerspace radius." }) });
    const { onClose } = renderSheet();
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("You're outside this makerspace's check-in area, so self check-in is refused.");
    expect(alert).toHaveTextContent("check-in kiosk");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("disables self check-in where no geofence is configured", () => {
    renderSheet({ selfCheckIn: false });
    expect(screen.getByText("Self check-in isn't set up here.", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check in" })).toBeDisabled();
  });

  it("offers the hide toggle only when personal opt-out is allowed", async () => {
    renderSheet();
    const toggle = screen.getByRole("switch", { name: /Hide me on the display/ });
    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(startCalls()).toHaveLength(1));
    expect(startBody()).toMatchObject({ hide_on_display: true });
  });

  it("says plainly that names are shown when opt-out is not allowed, and sends no hide flag", async () => {
    renderSheet({ optOutAllowed: false });
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.getByText(/display shows names, and hiding yours isn't offered here/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(startCalls()).toHaveLength(1));
    expect(startBody()).not.toHaveProperty("hide_on_display");
    expect(api.memberRequest.mock.calls.some(([path]) => String(path).endsWith("/preferences"))).toBe(false);
  });

  it("never reads durable preferences in a claim session", () => {
    renderSheet({ claim: true });
    expect(api.memberRequest.mock.calls.some(([path]) => String(path).endsWith("/preferences"))).toBe(false);
  });
});
