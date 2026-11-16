import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StaffOrganizationBookingForm } from "./StaffOrganizationBookingForm";
import type { BookableSpace } from "./bookingsApi";

const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest: mock.request }));
vi.mock("./StaffBookingAvailability", () => ({ StaffBookingAvailability: () => null }));

const space = { id: 4, makerspace_id: 2 } as BookableSpace;

beforeEach(() => {
  mock.request.mockReset();
  mock.request.mockImplementation(async (path: string) => path.endsWith("/choices/")
    ? [{ organization_id: 5, name: "Robotics club", contacts: [{ member_id: 8, name: "Ada" }] }]
    : { id: 30, status: "confirmed" });
});

it("books a space for an organization through its contact member", async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffOrganizationBookingForm makerspaceId={2} space={space} /></QueryClientProvider>);
  const submit = screen.getByRole("button", { name: "Create organization booking" });
  fireEvent.change(await screen.findByRole("combobox", { name: "Organization" }), { target: { value: "5" } });
  fireEvent.change(screen.getByRole("combobox", { name: "Contact" }), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("Starts (your local time)"), { target: { value: "2030-01-01T10:00" } });
  expect(submit).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Ends (your local time)"), { target: { value: "2030-01-01T12:00" } });
  fireEvent.click(submit);
  await waitFor(() => expect(mock.request).toHaveBeenCalledWith("/admin/spaces/4/organization-bookings/", {
    method: "POST", body: JSON.stringify({ organization_id: 5, contact_member_id: 8,
      starts_at: new Date("2030-01-01T10:00").toISOString(), ends_at: new Date("2030-01-01T12:00").toISOString(), note: "" }),
  }));
  expect(await screen.findByText("Booking created.")).toBeInTheDocument();
});
