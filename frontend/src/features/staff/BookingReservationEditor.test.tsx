import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BookingReservationEditor } from "./BookingReservationEditor";
import type { BookableSpace, Booking } from "./bookingsApi";
import type { CustomFormQuestion } from "../forms/customFormTypes";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request,
}));

const remaining: CustomFormQuestion = { id: "purpose", label: "Purpose", type: "short_text", required: true, options: [] };
const removed: CustomFormQuestion = { ...remaining, id: "equipment", label: "Equipment" };
const space: BookableSpace = {
  id: 8, makerspace_id: 3, public_token: "resource", name: "Workshop", kind: "bench", description: "",
  capacity: 1, location: "", image_url: "", is_public: false, show_public_availability: false,
  show_public_booker_names: false, approval_mode: "instant", payment_amount: "0.00",
  custom_form: [remaining, removed], requester_notifications_enabled: null,
  effective_requester_notifications_enabled: false, is_active: true, created_by_id: null,
  created_at: "2026-10-15T10:00:00Z", updated_at: "2026-10-15T10:00:00Z",
};
const booking: Booking = {
  id: 4, public_token: "reservation", space_id: 8, name: "Maker", email: "maker@example.test", phone: "",
  starts_at: "2099-10-16T10:00:00Z", ends_at: "2099-10-16T11:00:00Z", status: "confirmed",
  note: "Original note", payment: null, created_at: "2026-10-15T10:00:00Z",
  custom_answers: { version: 1, answers: [
    { ...remaining, value: "Build a chair" }, { ...removed, value: "Drill" },
  ] },
};

function setup() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const editor = (resource: BookableSpace) => <QueryClientProvider client={client}>
    <BookingReservationEditor space={resource} booking={booking} />
  </QueryClientProvider>;
  const view = render(editor(space));
  fireEvent.click(screen.getByRole("button", { name: "Edit note and answers" }));
  return (schema: BookableSpace["custom_form"]) => view.rerender(editor({ ...space, custom_form: schema }));
}

const save = () => screen.getByRole("button", { name: "Save reservation details" });

describe("reservation edits after live schema changes", () => {
  beforeEach(() => { request.mockReset(); request.mockResolvedValue(booking); });

  it("submits only current question IDs when an answer is edited after a question is removed", async () => {
    const changeSchema = setup();
    changeSchema([remaining]);
    expect(screen.queryByLabelText(/Equipment/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Build a table" } });
    fireEvent.click(save());
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/bookings/4/details/", {
      method: "PATCH", body: JSON.stringify({ custom_answers: { purpose: "Build a table" } }),
    }));
  });

  it("preserves unsaved answers to remaining questions across a schema refresh", async () => {
    const changeSchema = setup();
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Build a desk" } });
    changeSchema([remaining]);
    expect(screen.getByLabelText(/Purpose/)).toHaveValue("Build a desk");
    fireEvent.click(save());
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/bookings/4/details/", {
      method: "PATCH", body: JSON.stringify({ custom_answers: { purpose: "Build a desk" } }),
    }));
  });

  it("keeps a schema-only removal clean and allows a note-only save", async () => {
    const changeSchema = setup();
    changeSchema([remaining]);
    expect(save()).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reservation note"), { target: { value: "Updated note" } });
    fireEvent.click(save());
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/bookings/4/details/", {
      method: "PATCH", body: JSON.stringify({ note: "Updated note" }),
    }));
  });

  it.each([{ label: "null", schema: null }, { label: "empty", schema: [] }])("drops dirty deleted answers when the entire schema becomes $label", async ({ schema }) => {
    const changeSchema = setup();
    fireEvent.change(screen.getByLabelText(/Purpose/), { target: { value: "Unsaved answer" } });
    changeSchema(schema);
    expect(screen.queryByRole("group", { name: "Additional questions" })).not.toBeInTheDocument();
    expect(save()).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reservation note"), { target: { value: "Updated note" } });
    fireEvent.click(save());
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/bookings/4/details/", {
      method: "PATCH", body: JSON.stringify({ note: "Updated note" }),
    }));
  });
});
