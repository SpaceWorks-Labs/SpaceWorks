import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PresenceRoster } from "./PresenceRoster";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: api.staffRequest }));

const wrap = (ui: ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;
const now = Date.now();
const row = { account_id: 41, display_name: "Asha Rao", role_label: "Member", status: "working", project_id: null, hide_on_display: false,
  started_at: new Date(now - 3_600_000).toISOString(), expires_at: new Date(now + 3_600_000).toISOString(), ended_at: null, end_reason: "",
  active: true, names_displayed: true, personal_opt_out_allowed: true };
const iso = (offset: number) => new Date(now + offset).toISOString();
let related: unknown;

beforeEach(() => {
  api.staffRequest.mockReset();
  api.staffRequest.mockImplementation(async (path: string) => {
    if (path.includes("/presence-sessions/current")) return { count: 1, next: null, previous: null, results: [row] };
    if (path.endsWith("/presence-sessions/41/related")) return related;
    throw new Error(`unexpected ${path}`);
  });
});

describe("Presence related block", () => {
  it("shows the event, booking and machine sessions the server returned", async () => {
    related = {
      event: { event_id: 3, title: "Laser night", starts_at: iso(-3_600_000), ends_at: iso(3_600_000), registration_status: "attended" },
      booking: { booking_id: 8, space_name: "Workshop room", starts_at: iso(-1_800_000), ends_at: iso(3_600_000), arrived_at: iso(-300_000), status: "confirmed" },
      machine_sessions: [{ session_id: 5, machine_name: "Laser A", started_at: iso(-180_000), ended_at: null, source: "member_qr" }],
    };
    render(wrap(<PresenceRoster makerspaceId={5} />));
    fireEvent.click((await screen.findAllByRole("button", { name: "Related to Asha Rao" }))[0]);
    expect(await screen.findByText("Laser night")).toBeInTheDocument();
    expect(screen.getByText("Workshop room")).toBeInTheDocument();
    expect(screen.getByText(/Laser A/)).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspace/5/presence-sessions/41/related");
  });

  it("says so when nothing is linked or nothing is visible to this role", async () => {
    related = { event: null, booking: null, machine_sessions: [] };
    render(wrap(<PresenceRoster makerspaceId={5} />));
    fireEvent.click((await screen.findAllByRole("button", { name: "Related to Asha Rao" }))[0]);
    expect(await screen.findByText("Nothing else is linked to this check-in.")).toBeInTheDocument();
    expect(screen.queryByText("Event")).not.toBeInTheDocument();
  });
});
