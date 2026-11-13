import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TenantProvider } from "../../lib/tenant";
import { StructuredApiError } from "../../lib/api";
import { MemberEventTicketPage } from "./MemberEventTicketPage";

const mocks = vi.hoisted(() => ({ request: vi.fn(), blob: vi.fn(), save: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest: mocks.request, memberRequestBlob: mocks.blob, getAccessToken: () => "session",
}));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: { makerspace: { id: 7 } } }) }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Ticket account sign in</p> }));
vi.mock("./eventConfirmation", async () => ({ ...await vi.importActual<typeof import("./eventConfirmation")>("./eventConfirmation"), saveTicketBlob: mocks.save }));

const ticket = { registration_id: 4, status: "registered", ticket_png_available: true,
  event: { status: "published", title: "Workshop", description: "Public introduction", starts_at: "2026-11-01T10:00:00Z", ends_at: "2026-11-01T12:00:00Z", location: "Lab", public_token: "public-token", timezone_name: "UTC" } };
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/member/events/4/ticket"]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/events/:registrationId/ticket" element={<MemberEventTicketPage />} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { vi.clearAllMocks(); mocks.request.mockImplementation((path) => Promise.resolve(path === "/auth/me" ? { id: 19 } : ticket)); mocks.blob.mockResolvedValue(new Blob(["png"], { type: "image/png" })); });

describe("member event ticket", () => {
  it.each(["registered", "attended"])("downloads an authenticated PNG for %s", async (status) => {
    mocks.request.mockImplementation((path) => Promise.resolve(path === "/auth/me" ? { id: 19 } : { ...ticket, status })); show();
    fireEvent.click(await screen.findByRole("button", { name: "Download ticket PNG" }));
    await waitFor(() => expect(mocks.blob).toHaveBeenCalledWith("/member/makerspaces/7/event-registrations/4/ticket.png"));
    expect(mocks.save).toHaveBeenCalledWith(expect.any(Blob), "Workshop");
    const link = screen.getByRole("link", { name: "Add to Google Calendar" });
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    const url = new URL(link.getAttribute("href")!);
    expect(url.searchParams.get("text")).toBe("Workshop");
    expect(url.href).not.toContain("public-token"); expect(url.href).not.toContain("session");
  });
  it.each(["waitlisted", "pending_approval", "cancelled"])("withholds ticket and Google Calendar for %s", async (status) => {
    mocks.request.mockImplementation((path) => Promise.resolve(path === "/auth/me" ? { id: 19 } : { ...ticket, status, ticket_png_available: false })); show();
    await screen.findByRole("heading", { name: "Workshop" });
    expect(screen.queryByRole("button", { name: "Download ticket PNG" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Add to Google Calendar" })).toBeNull();
  });
  it("does not render another account's ticket when ownership is refused", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(404, { detail: "Not found." })); show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Ticket not found.");
    expect(screen.queryByRole("button", { name: "Download ticket PNG" })).toBeNull();
  });
  it.each(["registered", "attended"])("withholds Google Calendar for a cancelled event with a %s registration", async (status) => {
    mocks.request.mockImplementation((path) => Promise.resolve(path === "/auth/me" ? { id: 19 } : {
      ...ticket, status, ticket_png_available: false, event: { ...ticket.event, status: "cancelled" },
    })); show();
    await screen.findByRole("heading", { name: "Workshop" });
    expect(screen.queryByRole("link", { name: "Add to Google Calendar" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Download ticket PNG" })).toBeNull();
  });
  it("keeps Google Calendar available for an attended completed event", async () => {
    mocks.request.mockImplementation((path) => Promise.resolve(path === "/auth/me" ? { id: 19 } : {
      ...ticket, status: "attended", event: { ...ticket.event, status: "completed" },
    })); show();
    expect(await screen.findByRole("link", { name: "Add to Google Calendar" })).toBeVisible();
  });
  it("shows sign in for an unauthenticated account", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(401, { detail: "Sign in." })); show();
    expect(await screen.findByText("Ticket account sign in")).toBeVisible();
  });
  it("reports ticket render throttling", async () => {
    mocks.blob.mockRejectedValue(new StructuredApiError(429, { detail: "Please wait before downloading another ticket." })); show();
    fireEvent.click(await screen.findByRole("button", { name: "Download ticket PNG" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please wait before downloading another ticket.");
  });
});
