import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StepBookings } from "./StepBookings";
import { baseSpec, context, renderWithQuery } from "./test/stepTestKit";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async importOriginal => ({ ...(await importOriginal<object>()), staffRequest }));

const empty = { booking_slot_minutes: null, booking_buffer_before_minutes: null, booking_buffer_after_minutes: null, booking_approval_mode: "", training_notes: "", notes_at_session_start: false, notes_at_job_request: false, updated_at: null };
const saved = { ...empty, booking_slot_minutes: 45, booking_buffer_before_minutes: 5, booking_buffer_after_minutes: 5, booking_approval_mode: "instant", updated_at: "2026-11-01T00:00:00Z" };
const calls = (method: string, suffix: string) => staffRequest.mock.calls.filter(([path, init]) => (init?.method ?? "GET") === method && String(path).endsWith(suffix));
const serve = (setup: object, apply?: () => unknown) => staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
  if (path.endsWith("/apply-booking-defaults")) return apply ? apply() : { spaces: [] };
  if ((init?.method ?? "GET") === "PATCH") return { ...saved, ...JSON.parse(String(init?.body)), updated_at: "2026-11-02T00:00:00Z" };
  return setup;
});

describe("StepBookings", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("prefills from the template when nothing is saved, then saves the defaults", async () => {
    serve(empty);
    renderWithQuery(<StepBookings ctx={context({ spec: { ...baseSpec, bookings: { bookable: true, slot_minutes: 60, buffer_minutes: 10, requires_approval: true } } as never })} />);
    expect(await screen.findByLabelText("Slot length (minutes)")).toHaveValue("60");
    expect(screen.getByLabelText("Buffer before (minutes)")).toHaveValue("10");
    expect(screen.getByLabelText("Buffer after (minutes)")).toHaveValue("10");
    expect(screen.getByLabelText("Who approves a booking")).toHaveValue("approve");
    fireEvent.click(screen.getByRole("button", { name: "Save booking defaults" }));
    await waitFor(() => expect(calls("PATCH", "/machine-types/9/setup")).toHaveLength(1));
    expect(JSON.parse(calls("PATCH", "/machine-types/9/setup")[0][1].body)).toEqual({ booking_slot_minutes: 60, booking_buffer_before_minutes: 10, booking_buffer_after_minutes: 10, booking_approval_mode: "approve" });
  });

  it("keeps the saved values over the template and refuses an out-of-range slot", async () => {
    serve(saved);
    renderWithQuery(<StepBookings ctx={context({ spec: { ...baseSpec, bookings: { bookable: true, slot_minutes: 60 } } as never })} />);
    const slot = await screen.findByLabelText("Slot length (minutes)");
    expect(slot).toHaveValue("45");
    fireEvent.change(slot, { target: { value: "2000" } });
    expect(screen.getByText("Use a whole number from 1 to 1440.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save booking defaults" })).toBeDisabled();
  });

  it("confirms before applying to existing spaces and reports how many changed", async () => {
    serve(saved, () => ({ spaces: [4, 7] }));
    renderWithQuery(<StepBookings ctx={context()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Apply to existing spaces" }));
    expect(calls("POST", "/apply-booking-defaults")).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(calls("POST", "/apply-booking-defaults")).toHaveLength(1));
    expect(await screen.findByText("Updated 2 existing bookable spaces.")).toBeVisible();
  });

  it("shows a refusal from the bookings rules", async () => {
    serve(saved, () => { throw new Error("You do not have booking authority."); });
    renderWithQuery(<StepBookings ctx={context()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Apply to existing spaces" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("You do not have booking authority.")).toBeVisible();
  });
});
