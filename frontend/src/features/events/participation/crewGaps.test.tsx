import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const { request, saved } = vi.hoisted(() => ({ request: vi.fn(), saved: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: request }));
vi.mock("../../accountSavedDetails/api", () => ({ ownSavedDetails: saved }));
import { CrewSignupPage } from "./CrewSignupPage";
import { PublicPageSections } from "../../publicPages/PublicPageSections";
import { EventEditorialSections, eventEditorialTypes } from "../websiteSectionRegistry";
import { EventFunnel, type Funnel } from "../../staff/eventProgramme/EventFunnel";
import { MERGE_TAGS } from "../../staff/eventCredentials/layout";

function setup(node: ReactNode, path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>{node}</MemoryRouter></QueryClientProvider>);
}
const open = { event_id: 4, event_title: "Build night", starts_at: "2026-12-01T10:00:00Z", open: true, approval_required: true, crew: null };
beforeEach(() => { request.mockReset(); saved.mockReset(); });

describe("crew sign-up: catering prefill from Saved details (opt-in, #28)", () => {
  function page() {
    request.mockResolvedValue(open);
    return setup(<Routes><Route path="/crew/:eventId" element={<CrewSignupPage />} /></Routes>, "/crew/4");
  }

  it("never reads Saved details until the member asks", async () => {
    page();
    await screen.findByText("Join the crew");
    expect(saved).not.toHaveBeenCalled();
  });

  it("copies only the dietary field into the form and sends it with the sign-up", async () => {
    saved.mockResolvedValue({ version: 1, readiness: "ready", fields: [
      { field_key: "dietary_needs", value: "Vegetarian, no nuts" }, { field_key: "phone", value: "98765 43210" }] });
    page();
    fireEvent.click(await screen.findByRole("button", { name: "Use my Saved details" }));
    await screen.findByText("Filled from your Saved details. Edit it if needed.");
    const input = screen.getByLabelText(/Dietary needs/) as HTMLInputElement;
    expect(input.value).toBe("Vegetarian, no nuts");
    expect(screen.queryByDisplayValue("98765 43210")).toBeNull();
    request.mockResolvedValue({ ...open, crew: { id: 1, version: 1, crew_role: "", state: "applied", show_publicly: false } });
    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/events/4/crew-signup/", expect.objectContaining({ method: "POST" })));
    const post = request.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(JSON.parse(post[1].body)).toMatchObject({ dietary: "Vegetarian, no nuts" });
  });

  it("says so when Saved details hold no dietary needs or are unavailable", async () => {
    saved.mockResolvedValueOnce({ version: 1, readiness: "ready", fields: [] });
    page();
    fireEvent.click(await screen.findByRole("button", { name: "Use my Saved details" }));
    await screen.findByText("Your Saved details have no dietary needs.");
    saved.mockRejectedValueOnce(new Error("locked"));
    fireEvent.click(screen.getByRole("button", { name: "Use my Saved details" }));
    await screen.findByText("Your Saved details are not available right now.");
  });
});

describe("public crew as a Pages section (#128 C-36)", () => {
  const crew = { id: "11111111-1111-4111-8111-111111111111", type: "crew", enabled: true,
    payload: { title: "", results: [{ handle: "priya", display_name: "Priya", crew_role: "Mentor" }] } } as never;

  it("renders the crew cards with a profile link and role, titled Crew by default", () => {
    setup(<PublicPageSections sections={[crew]} image={() => null} />);
    expect(screen.getByRole("heading", { name: "Crew" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Priya" }).getAttribute("href")).toContain("/priya");
    expect(screen.getByText("Mentor")).toBeTruthy();
  });

  it("omits an empty crew section and is offered on event pages", () => {
    const empty = { ...(crew as object), payload: { title: "Our crew", results: [] } } as never;
    setup(<PublicPageSections sections={[empty]} image={() => null} />);
    expect(screen.queryByText("Our crew")).toBeNull();
    expect(eventEditorialTypes).toContain("crew");
  });

  it("renders through the event editorial registry", () => {
    setup(<EventEditorialSections projection={{ schema_version: 1, sections: [crew] }} image={() => null} />);
    expect(screen.getByText("Priya")).toBeTruthy();
  });
});

describe("crew chip and funnel stages", () => {
  it("offers the {{crewRole}} merge tag on credential badges", () => {
    expect(MERGE_TAGS).toContain("crewRole");
  });

  it("shows L21a application stages between responded and going (AN-c1)", () => {
    const data: Funnel = { event_id: 1, timezone_name: "UTC", caveat: "", reading: "", hint: "",
      capacity: { limit: null, going: 2, remaining: null, state: "unlimited" }, timeline: [],
      stages: [
        { key: "responded", label: "Responded", count: 10, denominator: 0, percent: null, stage_position: null },
        { key: "application_stage", label: "Screening", count: 8, denominator: 10, percent: 80, stage_position: 1 },
        { key: "application_stage", label: "Interview", count: 4, denominator: 8, percent: 50, stage_position: 2 },
        { key: "going", label: "Going", count: 2, denominator: 4, percent: 50, stage_position: null },
      ] };
    setup(<EventFunnel data={data} />);
    expect(screen.getByText("Stage 1: Screening")).toBeTruthy();
    expect(screen.getByText("Stage 2: Interview")).toBeTruthy();
    expect(screen.getByText("4 of 8 · 50%")).toBeTruthy();
  });
});
