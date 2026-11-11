// Decision 21 #9 (live ticket): the page re-reads the ticket on its own while a place is
// confirmed, flips the ticket to "checked in" when the desk records attendance, keeps the
// check-in code tied to a confirmed place, and stops polling for pending or refused tickets.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TenantProvider } from "../../lib/tenant";
import { StructuredApiError } from "../../lib/api";
import { MemberEventTicketPage } from "./MemberEventTicketPage";

const mocks = vi.hoisted(() => ({ request: vi.fn(), blob: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest: mocks.request, memberRequestBlob: mocks.blob, getAccessToken: () => "session",
}));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: { makerspace: { id: 7 } } }) }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Ticket account sign in</p> }));
// The photo consent panel has its own suite and its own endpoints; keep this test to the ticket.
vi.mock("./eventPresentation/PhotoChoice", () => ({ PhotoChoice: () => null }));

const TICKET_PATH = "/member/makerspaces/7/event-registrations/4/ticket/";
const base = { registration_id: 4, status: "registered", ticket_png_available: true, attended_at: null,
  event: { id: 9, status: "published", title: "Workshop", description: "", starts_at: "2026-11-01T10:00:00Z",
    ends_at: "2026-11-01T12:00:00Z", location: "Lab", public_token: "public-token", timezone_name: "UTC" } };

/** Each poll returns the next queued server state; the last one repeats. */
function serve(...states: Array<Record<string, unknown> | Error>) {
  const queue = [...states];
  mocks.request.mockImplementation((path: string) => {
    if (path === "/auth/me") return Promise.resolve({ id: 19 });
    if (path !== TICKET_PATH) return Promise.reject(new Error(`unexpected ${path}`));
    const next = queue.length > 1 ? queue.shift()! : queue[0];
    return next instanceof Error ? Promise.reject(next) : Promise.resolve({ ...base, ...next });
  });
}
const ticketReads = () => mocks.request.mock.calls.filter(([path]) => path === TICKET_PATH).length;
const ticketState = () => screen.getByText(/Checked in|Ready for event check-in/).closest("[data-ticket-state]");

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/member/events/4/ticket"]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}
async function advance(ms: number) { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); }

beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.useRealTimers(); });

describe("live member ticket", () => {
  it("refetches a confirmed ticket and tears it when the desk records attendance", async () => {
    serve({}, { status: "attended", attended_at: "2026-11-01T10:05:00Z" });
    show();
    expect(await screen.findByText("Ready for event check-in")).toBeInTheDocument();
    expect(ticketState()).toHaveAttribute("data-ticket-state", "intact");
    expect(screen.getByText("Your check-in code is on the downloadable ticket.")).toBeInTheDocument();
    const before = ticketReads();
    await advance(5100);
    expect(await screen.findByText("Checked in")).toBeInTheDocument();
    expect(ticketReads()).toBeGreaterThan(before);
    expect(ticketState()).toHaveAttribute("data-ticket-state", "torn");
    expect(screen.getByText("Checked in").parentElement?.querySelector("time")).toHaveAttribute("dateTime", "2026-11-01T10:05:00Z");
    // Attendance is recorded, but the ticket (and its code) stay downloadable for the badge.
    expect(screen.getByRole("button", { name: "Download ticket PNG" })).toBeInTheDocument();
  });

  it("follows an undone check-in back to an intact ticket on the next poll", async () => {
    serve({ status: "attended", attended_at: "2026-11-01T10:05:00Z" }, { status: "registered", attended_at: null });
    show();
    expect(await screen.findByText("Checked in")).toBeInTheDocument();
    await advance(5100);
    expect(await screen.findByText("Ready for event check-in")).toBeInTheDocument();
    expect(ticketState()).toHaveAttribute("data-ticket-state", "intact");
  });

  it.each(["pending_approval", "waitlisted"])("does not poll or show a check-in code while %s", async (status) => {
    serve({ status, ticket_png_available: false });
    show();
    expect(await screen.findByText("Your check-in code appears once the makerspace confirms your place.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download ticket PNG" })).toBeNull();
    const before = ticketReads();
    await advance(16000);
    expect(ticketReads()).toBe(before);
  });

  it("stops polling once the server refuses the ticket (module off, cancelled or no longer owned)", async () => {
    serve({}, new StructuredApiError(404, { detail: "Not found.", code: "module_disabled", module: "events" }));
    show();
    expect(await screen.findByText("Ready for event check-in")).toBeInTheDocument();
    await advance(5100);
    expect(await screen.findByRole("alert")).toHaveTextContent("Ticket not found.");
    expect(screen.queryByText("Ready for event check-in")).toBeNull();
    expect(screen.queryByRole("button", { name: "Download ticket PNG" })).toBeNull();
    const after = ticketReads();
    await advance(16000);
    expect(ticketReads()).toBe(after);
  });
});
