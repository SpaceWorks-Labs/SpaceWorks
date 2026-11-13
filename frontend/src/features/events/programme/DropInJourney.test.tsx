import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: request, staffRequest: request }));
import { DropInJourney } from "./DropInJourney";
import { availableJourneys } from "./EventProgrammePage";
import { HelpComposer } from "../contributions/HelpComposer";

const scope = { accountId: 7, eventId: 11, makerspaceId: 3 };
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
function setup(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>);
}
function context(kind: string, mentoring: boolean) {
  return { programme: { kind, capabilities: { "events.hackathons": kind === "hackathon", "events.mentoring": mentoring,
    "events.volunteering": false }, finder_enabled: false }, routes: { role_postings: null } } as never;
}
beforeEach(() => { request.mockReset(); });

describe("Mentor Desk on any event (#128 C-36, E2-f)", () => {
  it("offers help and office hours on an ordinary event once events.mentoring is on", () => {
    const names = (kind: string, on: boolean) => availableJourneys(context(kind, on)).map(row => row.suffix);
    expect(names("ordinary", true)).toEqual(expect.arrayContaining(["help", "office-hours"]));
    expect(names("ordinary", false)).not.toContain("help");
    // A hackathon keeps its team journey: help sits beside team and project, as before.
    expect(names("hackathon", true)).toEqual(expect.arrayContaining(["team", "project", "help", "office-hours"]));
  });

  it("asks a mentor without a team: no team picker and no team_id in the request", async () => {
    request.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/help-topics/")) return Promise.resolve({ results: [{ key: "code", label: "Code" }] });
      if (init?.method === "POST") return Promise.resolve({ id: 1, version: 1, allowed_actions: [] });
      return Promise.resolve(page([]));
    });
    setup(<DropInJourney scope={scope} section="help" />);
    await screen.findByText("Ask a mentor");
    expect(screen.queryByLabelText("Team")).toBeNull();
    fireEvent.change(screen.getByLabelText("What do you need help with?"), { target: { value: "My board will not flash" } });
    fireEvent.click(screen.getByRole("button", { name: "Request help" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(expect.stringContaining("/events/11/help/"),
      expect.objectContaining({ method: "POST" })));
    const post = request.mock.calls.find(([, init]) => init?.method === "POST")!;
    const body = JSON.parse(post[1].body);
    expect(body).not.toHaveProperty("team_id");
    expect(body).toMatchObject({ type_key: "code", summary: "My board will not flash", expected_version: 0 });
  });

  it("keeps the team picker and team_id for a hackathon team", async () => {
    request.mockResolvedValue({ id: 1, version: 1, allowed_actions: [] });
    setup(<HelpComposer scope={scope} surface="member" teams={[{ id: 5, label: "Night Owls" }]} categories={[{ key: "code", label: "Code" }]} />);
    expect(screen.getByLabelText("Team")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("What do you need help with?"), { target: { value: "Stuck" } });
    fireEvent.click(screen.getByRole("button", { name: "Request help" }));
    await waitFor(() => expect(request).toHaveBeenCalled());
    expect(JSON.parse(request.mock.calls[0][1].body)).toMatchObject({ team_id: 5 });
  });

  it("books an office-hour slot for oneself without a team", async () => {
    request.mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve({ id: 9, version: 1, allowed_actions: ["cancel"] });
      return Promise.resolve(page([{ id: 4, version: 2, task: "Electronics clinic", starts_at: "2026-12-01T10:00:00Z",
        ends_at: "2026-12-01T11:00:00Z", available: 3 }]));
    });
    setup(<DropInJourney scope={scope} section="office-hours" />);
    fireEvent.click(await screen.findByRole("button", { name: "Book a place" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(expect.stringContaining("/office-hours/4/bookings/"),
      expect.objectContaining({ method: "POST" })));
    const post = request.mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(JSON.parse(post[1].body)).not.toHaveProperty("team_id");
  });
});
