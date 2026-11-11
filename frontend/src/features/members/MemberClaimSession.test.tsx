import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getAccessToken, memberRequest } from "../../lib/api";
import { locationPermission, readLocation } from "../presence/location";
import { hasClaimSession, MemberClaimSession } from "./MemberClaimSession";
vi.mock("../../lib/api", () => ({ memberRequest: vi.fn(), getAccessToken: vi.fn() }));
vi.mock("../presence/location", async (original) => ({ ...await original<typeof import("../presence/location")>(), locationPermission: vi.fn(), readLocation: vi.fn() }));
function show(modules = ["public_inventory"], geofenceEnabled = false) { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><MemberClaimSession slug="workshop" makerspaceId={3} modules={modules} geofenceEnabled={geofenceEnabled} name="Workshop" /></MemoryRouter></QueryClientProvider>); }
const reading = { latitude: 12.97, longitude: 77.59, accuracy: 12 };
describe("MemberClaimSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(locationPermission).mockResolvedValue("granted");
    vi.mocked(readLocation).mockResolvedValue({ ok: true, reading });
  });
  it("recognizes a claim token for UI discovery without accepting malformed tokens", () => {
    vi.mocked(getAccessToken).mockReturnValue(`header.${btoa(JSON.stringify({ token_type: "claim_access" }))}.signature`); expect(hasClaimSession()).toBe(true);
    vi.mocked(getAccessToken).mockReturnValue("invalid"); expect(hasClaimSession()).toBe(false);
  });
  it("opens presence and shows a staff-witness waiver without forbidden global queries", async () => {
    vi.mocked(memberRequest).mockImplementation((path, options) => {
      if (path === "/member/makerspaces/3/waiver") return Promise.resolve({ has_waiver: true, version: "v1", body: "Be careful" }) as ReturnType<typeof memberRequest>;
      if (path === "/public/workshop/presence-sessions/current") return Promise.resolve({ active: false, session: null, presets: [60, 120, 180, 240] }) as ReturnType<typeof memberRequest>;
      if (path === "/public/workshop/presence-sessions/projects") return Promise.resolve({ count: 0, results: [] }) as ReturnType<typeof memberRequest>;
      if (path === "/public/workshop/presence-sessions" && options?.method === "POST") return Promise.resolve({
        active: true, status: "visiting", started_at: new Date().toISOString(), expires_at: new Date(Date.now() + 120 * 60_000).toISOString(),
        ended_at: null, end_reason: "", project_id: null, hide_on_display: false, names_displayed: true, personal_opt_out_allowed: true,
      }) as ReturnType<typeof memberRequest>;
      throw new Error(`Unexpected claim-session request: ${path}`);
    });
    show(["public_inventory", "presence"], true);
    await screen.findByRole("button", { name: "Check in" });
    expect(screen.getByRole("link", { name: "Browse tools" })).toHaveAttribute("href", "/m/workshop");
    expect(await screen.findByText("Be careful")).toBeVisible(); expect(screen.queryByText("Accept waiver")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    const sheet = screen.getByRole("dialog", { name: "Check in" });
    expect(within(sheet).getByRole("radio", { name: "2 h" })).toHaveAttribute("aria-checked", "true");
    expect(readLocation).not.toHaveBeenCalled();
    fireEvent.click(within(sheet).getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/public/workshop/presence-sessions", { method: "POST", body: JSON.stringify({ duration_minutes: 120, ...reading, status: "visiting", hide_on_display: false }) }));
    expect(await screen.findByText("Checked in")).toBeVisible();
    expect(memberRequest).not.toHaveBeenCalledWith("/memberships/me"); expect(memberRequest).not.toHaveBeenCalledWith("/member/archived-payments");
    expect(memberRequest).not.toHaveBeenCalledWith("/auth/me");
    expect(memberRequest).not.toHaveBeenCalledWith("/public/workshop/presence-sessions/preferences");
    expect(new Set(vi.mocked(memberRequest).mock.calls.map(([path]) => path))).toEqual(new Set([
      "/member/makerspaces/3/waiver", "/public/workshop/presence-sessions/current",
      "/public/workshop/presence-sessions/projects", "/public/workshop/presence-sessions",
    ]));
  });
  it("keeps the waiver available without querying presence when its module is off", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ has_waiver: true, version: "v1", body: "Be careful" });
    show();
    expect(await screen.findByText("Be careful")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Presence" })).toBeNull();
    expect(vi.mocked(memberRequest).mock.calls.map(([path]) => path)).toEqual(["/member/makerspaces/3/waiver"]);
  });
  it("requires staff check-in when the geofence is not configured", async () => {
    vi.mocked(memberRequest).mockImplementation((path) => Promise.resolve(path.includes("waiver") ? { has_waiver: false } : { active: false, session: null }) as ReturnType<typeof memberRequest>);
    show(["presence"]);
    fireEvent.click(await screen.findByRole("button", { name: "Check in" }));
    const sheet = screen.getByRole("dialog", { name: "Check in" });
    expect(within(sheet).getByRole("button", { name: "Check in" })).toBeDisabled();
    expect(within(sheet).getByText("Self check-in isn't set up here.")).toBeVisible();
    expect(readLocation).not.toHaveBeenCalled();
    expect(vi.mocked(memberRequest).mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  });
  it("shows an expired session error", async () => { vi.mocked(memberRequest).mockRejectedValue(new Error("Claim session is no longer active")); show(); expect(await screen.findByRole("alert")).toHaveTextContent("no longer active"); });
});
