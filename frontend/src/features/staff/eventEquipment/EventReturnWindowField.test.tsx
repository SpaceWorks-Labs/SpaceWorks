import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { EventReturnWindowField } from "./EventReturnWindowField";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest }));

function show(hours: number | null) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><EventReturnWindowField makerspaceId={3} eventId={9} hours={hours} /></QueryClientProvider>);
  return invalidate;
}
const field = () => screen.getByLabelText(/Items due N hours after the event ends/);

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue({ equipment_return_hours: 24 }); });

it("saves the hours and refreshes the desk", async () => {
  const invalidate = show(null);
  expect(field()).toHaveValue(null);
  fireEvent.change(field(), { target: { value: "24" } });
  fireEvent.click(screen.getByRole("button", { name: "Save return window" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/events/9/equipment-desk",
    { method: "PATCH", body: JSON.stringify({ equipment_return_hours: 24 }) }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["event-equipment-desk", 3, 9] }));
});

it("clears back to the event end with a blank value", async () => {
  show(6);
  fireEvent.change(field(), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Save return window" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/events/9/equipment-desk",
    { method: "PATCH", body: JSON.stringify({ equipment_return_hours: null }) }));
});

it("refuses hours outside 0 to 720 before sending", () => {
  show(null);
  fireEvent.change(field(), { target: { value: "721" } });
  expect(screen.getByRole("alert")).toHaveTextContent("from 0 to 720");
  expect(screen.getByRole("button", { name: "Save return window" })).toBeDisabled();
  expect(staffRequest).not.toHaveBeenCalled();
});
