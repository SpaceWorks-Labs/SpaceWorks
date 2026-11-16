// Open item B9: the venue fee picks the payer and room by name and shows the double-charge refusal.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest: request }));

import { EventVenueFeeForm } from "./EventVenueFeeForm";

function renderForm() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><EventVenueFeeForm eventId={4} /></MemoryRouter></QueryClientProvider>);
}

let put: unknown;
beforeEach(() => {
  put = undefined;
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.includes("venue-fee") && init?.method === "PUT") {
      put = JSON.parse(String(init.body));
      throw new StructuredApiError(409, { detail: "A booking already holds this room during the event.", code: "venue_room_already_booked" });
    }
    if (path.includes("venue-fee")) throw new StructuredApiError(404, { detail: "Not found." });
    if (path.includes("speaker-candidates")) return { results: [{ id: 21, display_name: "Ola Organiser", username: "ola", relation: "member" }] };
    if (path.includes("event-room-choices")) return { results: [{ id: 6, name: "Hall", capacity: 40, needs_approval: false, status: "available" }] };
    return { id: 4, makerspace_id: 3, title: "Meetup", staff_permissions: [] };
  });
});

describe("venue fee pickers", () => {
  it("sends the picked payer and room ids and shows the clash refusal", async () => {
    renderForm();
    const room = await screen.findByRole("option", { name: "Hall (fits 40)" });
    expect(screen.queryByLabelText(/Payer account number/)).toBeNull();
    expect(screen.getByRole("button", { name: "Save venue fee" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Who pays"), { target: { value: "ol" } });
    fireEvent.mouseDown(await screen.findByRole("option", { name: /Ola Organiser/ }, { timeout: 2000 }));
    fireEvent.change(room.closest("select")!, { target: { value: "6" } });
    fireEvent.click(screen.getByRole("button", { name: "Save venue fee" }));
    await waitFor(() => expect(put).toEqual(expect.objectContaining({ payer_id: 21, room_id: 6, mode: "inherit" })));
    expect(await screen.findByRole("alert")).toHaveTextContent(/already holds this room/);
    expect(request).toHaveBeenCalledWith(expect.stringContaining("/admin/makerspace/3/event-room-choices"), expect.anything());
  });
});
