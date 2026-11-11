import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: request, staffRequest: request }));
import { criteriaFrom } from "./ReviewStagesPanel";
import { ParticipationChips } from "./RosterParticipation";
import { CheckInListsPanel } from "./CheckInListsPanel";
import { eventDrawerSurfaces } from "../eventDrawerTabs";
import { AttendanceReplyPage } from "../../events/participation/AttendanceReplyPage";

function setup(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}
const access = { manager: false, edit: false, registrations: true, invitations: false, checkIn: true, publish: false,
  applications: true, hackathon: false, teams: false, volunteers: true, mentors: false, judge: false, sponsor: false, reimbursements: false };
beforeEach(() => { request.mockReset(); });

describe("lane L21a staff surfaces", () => {
  it("turns criteria labels into unique, valid keys", () => {
    expect(criteriaFrom(["Motivation", "Motivation", "3D printing"])).toEqual([
      { key: "motivation", label: "Motivation" }, { key: "motivation_1", label: "Motivation" },
      { key: "c_3d_printing", label: "3D printing" }]);
  });

  it("shows applications on any event with events.applications and crew/lists only with their switches", () => {
    const event = { status: "published", ticketing_features: [] } as never;
    const off = eventDrawerSurfaces(event, access as never, []).sections;
    expect(off.applications).toBe(false);
    expect(off.crew).toBe(false);
    expect(off["checkin-lists"]).toBe(false);
    const on = eventDrawerSurfaces(event, access as never, ["events.applications", "events.crew", "events.checkin_lists",
      "events.attendance_confirmation"]).sections;
    expect(on.applications && on.crew && on["checkin-lists"] && on.broadcasts).toBe(true);
  });

  it("marks crew places and attendance replies in the guest list", () => {
    render(<ParticipationChips row={{ id: 1, status: "registered", is_crew: true,
      attendance_reply: { answer: "no", note: "sick", replied_at: null, effect: "none" } }} />);
    expect(screen.getByText("Crew")).toBeTruthy();
    expect(screen.getByText(/Not coming · note/)).toBeTruthy();
  });

  it("records a collection and explains a refusal without touching entry check-in", async () => {
    request.mockImplementation((path: string, init?: RequestInit) => {
      if (!init) return Promise.resolve([{ id: 5, event_id: 9, name: "Lunch", kind: "meal", after_entry: true, addon_id: null,
        addon_name: null, per_person: 1, archived: false, collected: 0 }]);
      expect(path).toBe("/admin/events/9/checkin-lists/5/scan/");
      return Promise.reject(Object.assign(new Error("refused"), { code: "entry_required" }));
    });
    setup(<CheckInListsPanel eventId={9} canManage={false} addons={[]} />);
    fireEvent.click(await screen.findByRole("button", { name: "Collect" }));
    fireEvent.change(screen.getByLabelText("Registration number"), { target: { value: "44" } });
    fireEvent.click(screen.getByRole("button", { name: "Record collection" }));
    expect(await screen.findByText("Check them in at the door first.")).toBeTruthy();
  });
});

describe("the private attendance reply page", () => {
  it("answers No with a note and shows what happened to the place", async () => {
    const base = { event_id: 3, event_title: "Build night", starts_at: "2026-11-10T18:00:00Z", registration_id: 8,
      answer: null, note: "", replied_at: null, effect: "none", free_on_no: true };
    request.mockImplementation((_path: string, init?: RequestInit) => init
      ? Promise.resolve({ ...base, answer: "no", note: "away", effect: "released" }) : Promise.resolve(base));
    setup(<MemoryRouter initialEntries={["/member/events/3/attendance"]}><Routes>
      <Route path="/member/events/:eventId/attendance" element={<AttendanceReplyPage />} /></Routes></MemoryRouter>);
    expect(await screen.findByText(/your place goes to someone else/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/A note for the organisers/), { target: { value: "away" } });
    fireEvent.click(screen.getByRole("button", { name: "No, I can't come" }));
    await waitFor(() => expect(screen.getByText(/released for someone on the waitlist/)).toBeTruthy());
    expect(request).toHaveBeenLastCalledWith("/events/3/attendance/", expect.objectContaining({ method: "POST" }));
  });
});
