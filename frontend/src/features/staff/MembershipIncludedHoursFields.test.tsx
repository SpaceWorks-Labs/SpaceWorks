import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { includedHoursInput, validateIncludedHours } from "./MembershipIncludedHoursFields";
import { MembershipPlansSection } from "./MembershipPlansSection";
import { StaffListContext } from "./StaffListContext";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest }));
vi.mock("./useStaffChargesOn", () => ({ useStaffChargesOn: () => true }));
vi.mock("./pricing/PricingNote", () => ({ PlanPriceNote: () => null }));

const plan = { id: 4, name: "Studio", interval: "monthly", custom_days: null, amount: "10.00", currency: "usd", is_active: true,
  included_booking_hours: 5, included_machine_hours: 2, created_at: "", updated_at: "" };

function wrap(node: ReactNode, modules: string[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><StaffListContext.Provider value={{ ownerName: "", canShare: false,
    makerspace: { id: 7, enabled_modules: modules } }}>{node}</StaffListContext.Provider></QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method ? plan : [plan]);
});

it("validates and sends only the pools the space can use", () => {
  expect(validateIncludedHours({ booking: "8784", machine: "0" })).toBeNull();
  expect(validateIncludedHours({ booking: "8785", machine: "0" })).toMatch(/0 to 8784/);
  expect(validateIncludedHours({ booking: "1.5", machine: "0" })).toMatch(/whole number/);
  expect(includedHoursInput({ booking: "3", machine: "4" }, { booking: true, machine: false })).toEqual({ included_booking_hours: 3 });
  expect(includedHoursInput({ booking: "3", machine: "4" }, { booking: false, machine: false })).toEqual({});
});

it("edits a plan's included hours when bookings and machines run", async () => {
  wrap(<MembershipPlansSection makerspaceId={7} />, ["membership", "bookings", "machines"]);
  fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
  expect(screen.getByLabelText("Room booking hours per term")).toHaveValue(5);
  fireEvent.change(screen.getByLabelText("Machine time hours per term"), { target: { value: "6" } });
  fireEvent.click(screen.getByRole("button", { name: "Save plan" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/membership-plans/4", expect.objectContaining({ method: "PATCH" })));
  const body = JSON.parse(String(staffRequest.mock.calls.find(([, init]) => init?.method === "PATCH")?.[1]?.body));
  expect(body).toMatchObject({ included_booking_hours: 5, included_machine_hours: 6 });
});

it("hides included hours while bookings is off", async () => {
  wrap(<MembershipPlansSection makerspaceId={7} />, ["membership"]);
  await screen.findByRole("button", { name: "Edit" });
  expect(screen.queryByText("Included hours")).toBeNull();
});
