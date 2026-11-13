import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));

import { EventTicketsPanel } from "./EventTicketsPanel";

const ticket = { id: 5, name: "Standard", amount: "10.00", audience: "public", capacity: 40, sales_start_at: null, sales_end_at: null, is_active: true, registration_count: 2 };
let deleteResult: () => Promise<unknown>;

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><EventTicketsPanel eventId={4} /></QueryClientProvider>);
}

beforeEach(() => {
  request.mockReset();
  deleteResult = () => Promise.resolve(undefined);
  request.mockImplementation((path: string, options?: RequestInit) => {
    if (path.startsWith("/admin/events/4/ticket-types/?page=")) return Promise.resolve({ count: 1, next: null, previous: null, results: [ticket] });
    if (options?.method === "DELETE") return deleteResult();
    if (options?.method === "PATCH") return Promise.resolve({ ...ticket, ...JSON.parse(String(options.body)) });
    return Promise.resolve({});
  });
});

describe("ticket types", () => {
  it("shows the registration count and edits only the changed fields", async () => {
    setup();
    expect(await screen.findByText(/2 registered/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Edit Standard" }));
    const form = screen.getByRole("form", { name: "Edit Standard" });
    // A type in use keeps its price and audience; the server would refuse the change.
    expect(within(form).getByLabelText("Price")).toBeDisabled();
    expect(within(form).getByLabelText("Ticket audience")).toBeDisabled();
    fireEvent.change(within(form).getByLabelText("Ticket name"), { target: { value: "Early bird" } });
    fireEvent.change(within(form).getByLabelText(/Ticket capacity/), { target: { value: "50" } });
    fireEvent.click(within(form).getByLabelText("Available for new registrations"));
    fireEvent.click(within(form).getByRole("button", { name: "Save ticket type" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-ticket-types/5/", {
      method: "PATCH", body: JSON.stringify({ name: "Early bird", capacity: 50, is_active: false }),
    }));
  });

  it("deletes after confirmation", async () => {
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "Delete Standard" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete ticket type" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-ticket-types/5/", { method: "DELETE" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("offers Deactivate instead when registrations reference the type", async () => {
    deleteResult = () => Promise.reject(new StructuredApiError(409, { detail: "Registrations use this ticket type.", code: "ticket_type_referenced" }));
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "Delete Standard" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete ticket type" }));
    expect(await screen.findByText("Registrations use this ticket type.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Deactivate instead" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-ticket-types/5/", { method: "PATCH", body: JSON.stringify({ is_active: false }) }));
  });
});
