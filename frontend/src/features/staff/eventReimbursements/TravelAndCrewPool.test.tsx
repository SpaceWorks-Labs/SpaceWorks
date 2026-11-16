import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { BookedTravelActions, canBookTravel, CrewPoolPanel, isBookedTravel, type ScreeningRow } from "./TravelAndCrewPool";

const mutate = vi.hoisted(() => vi.fn());
const programme = vi.hoisted(() => ({ data: { initialized: true, currency: "INR", allowed_actions: [], pools: [] as unknown[] } }));
vi.mock("../../events/stagedForms/privateQueries", () => ({ commandError: () => "error",
  usePrivateCommand: () => ({ mutate, isPending: false, error: null, isSuccess: false }) }));
vi.mock("./api", () => ({ reimbursementAdminKey: () => ["k"], reimbursementAdminPath: () => "/admin/events/41/reimbursements/",
  useProgramme: () => programme }));
afterEach(() => { mutate.mockReset(); });

const scope = { actorId: 1, makerspaceId: 2, eventId: 41 };
const row: ScreeningRow = { id: 7, version: 2, state: "requested", currency: "INR", budget: { pool_id: 1, pool_version: 4, available_minor: 900000 }, award: null };

describe("crew pool (G14)", () => {
  it("creates the one crew pool with expected_version 0", () => {
    render(<CrewPoolPanel scope={scope} />);
    fireEvent.change(screen.getByLabelText("Crew pool total (INR)"), { target: { value: "500" } });
    fireEvent.click(screen.getByRole("button", { name: "Create crew pool" }));
    expect(mutate).toHaveBeenCalledWith({ path: "/admin/events/41/reimbursements/crew-pool/", body: { expected_version: 0, initial_total_minor: 50000 } });
  });
});

describe("organiser-booked travel (G12)", () => {
  it("knows which requests can be booked and which are booked", () => {
    expect(canBookTravel(row)).toBe(true);
    expect(canBookTravel({ ...row, award: { id: 1, state: "accepted", amount_minor: 1 } })).toBe(false);
    expect(isBookedTravel({ ...row, award: { id: 1, state: "closed", amount_minor: 1, reason_code: "direct_booking" } })).toBe(true);
  });

  it("records a booking against the request's pool version", () => {
    render(<BookedTravelActions scope={scope} row={row} />);
    fireEvent.click(screen.getByRole("button", { name: "Record booked travel" }));
    fireEvent.change(screen.getByLabelText("Cost (INR)"), { target: { value: "4200.00" } });
    fireEvent.change(screen.getByLabelText(/Vendor/), { target: { value: "IndiGo" } });
    fireEvent.click(screen.getByRole("button", { name: "Record booking" }));
    expect(mutate).toHaveBeenCalledWith({ path: "/admin/events/41/reimbursements/requests/7/direct-booking/",
      body: expect.objectContaining({ expected_version: 2, expected_pool_version: 4, amount_minor: 420000, currency: "INR", vendor: "IndiGo" }) },
      expect.anything());
  });
});
