import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest }));

import { MembersPanel } from "./MembersPanel";

const event = (id: number, title: string) => ({ id, title, starts_at: "2026-09-01T10:00:00Z", ends_at: "2026-09-01T12:00:00Z", location: "Lab", status: "completed" });
const history = {
  counts: { registered: 4, attended: 3, cancelled: 1, speaking: 1 },
  registrations: [{ registration_id: 11, status: "attended", event: event(1, "Soldering basics") }],
  speaking: [{ speaker_id: 21, role: "speaker", occurred_at: "2026-08-01T10:00:00Z", event: event(2, "Laser safety talk") }],
};
let historyResult: () => Promise<unknown>;

function panel() {
  render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MembersPanel makerspaceId={7} membershipEnabled actorActions={["manage_members"]} isSuperadmin={false} onAuthRefresh={() => {}} />
  </QueryClientProvider></MemoryRouter>);
}

beforeEach(() => {
  staffRequest.mockReset();
  historyResult = () => Promise.resolve(history);
  staffRequest.mockImplementation((url: string) => {
    if (url.startsWith("/admin/memberships?")) return Promise.resolve({ results: [{
      id: 1, status: "active", user: { id: 2, username: "maya", display_name: "Maya" }, assigned_role: null, role_ids: [], roles: [],
      verified_at: null, can_refer: false, can_verify: false, waiver_required: false, payment: null,
    }], count: 1, next: null, previous: null });
    if (url === "/admin/makerspaces/7/members/2/events/") return historyResult();
    if (url.startsWith("/admin/membership-requests?")) return Promise.resolve({ results: [], count: 0, next: null, previous: null });
    return Promise.resolve([]);
  });
});

describe("member drawer events", () => {
  it("fetches only once the drawer opens, then shows counts, talks and registrations", async () => {
    panel();
    await screen.findByText("Maya");
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspaces/7/members/2/events/");
    fireEvent.click(screen.getByText("Maya"));
    expect(await screen.findByRole("heading", { name: "Events" })).toBeVisible();
    expect(await screen.findByText("Laser safety talk")).toBeVisible();
    expect(screen.getByText("Soldering basics")).toBeVisible();
    const attended = screen.getAllByText("Attended").find((node) => node.tagName === "DT")!;
    expect(attended.nextSibling?.textContent).toBe("3");
    expect(screen.getByRole("heading", { name: "Spoke at" })).toBeVisible();
  });

  it("disappears for a viewer without events or members authority", async () => {
    historyResult = () => Promise.reject(new StructuredApiError(403, { detail: "Forbidden" }));
    panel();
    fireEvent.click(await screen.findByText("Maya"));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/members/2/events/"));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Events" })).toBeNull());
  });

  it("shows an empty state for a member with no events", async () => {
    historyResult = () => Promise.resolve({ counts: { registered: 0, attended: 0, cancelled: 0, speaking: 0 }, registrations: [], speaking: [] });
    panel();
    fireEvent.click(await screen.findByText("Maya"));
    expect(await screen.findByText("No events here yet.")).toBeVisible();
  });
});
