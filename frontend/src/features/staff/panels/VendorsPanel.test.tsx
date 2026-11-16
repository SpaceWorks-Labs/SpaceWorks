import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { VendorsPanel } from "./VendorsPanel";
import type { Vendor } from "./vendorsApi";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));

const vendor: Vendor = { id: 3, name: "Robu", contact_name: "Asha", email: "sales@robu.test", phone: "", website: "", notes: "",
  is_archived: false, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z" };

beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async (_path: string, init?: RequestInit) => init?.method ? { ...vendor, ...JSON.parse(String(init.body)) } : [vendor]);
});

const onBack = vi.fn();
function setup() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><VendorsPanel makerspaceId={7} onBack={onBack} /></MemoryRouter>
  </QueryClientProvider>);
}

it("lists live vendors with their contact details and links back to To-Buy", async () => {
  setup();
  expect(await screen.findByText("Robu")).toBeInTheDocument();
  expect(screen.getByText("Asha · sales@robu.test")).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/procurement/makerspace/7/vendors");
  fireEvent.click(screen.getAllByRole("button", { name: "Back to To-Buy" })[0]);
  expect(onBack).toHaveBeenCalled();
});

it("adds a vendor", async () => {
  setup();
  await screen.findByText("Robu");
  fireEvent.click(screen.getAllByRole("button", { name: "Add vendor" })[0]);
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Company name"), { target: { value: "Makers Mart" } });
  fireEvent.change(within(dialog).getByLabelText("Email"), { target: { value: "hi@mart.test" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Add vendor" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/procurement/makerspace/7/vendors", expect.objectContaining({ method: "POST",
    body: expect.stringContaining('"name":"Makers Mart"') })));
});

it("archives a vendor after confirming, and reads archived ones on their tab", async () => {
  setup();
  await screen.findByText("Robu");
  fireEvent.click(screen.getByRole("button", { name: "Actions for Robu" }));
  fireEvent.click(screen.getByRole("menuitem", { name: /Archive/ }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Archive" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/procurement/makerspace/7/vendors/3", { method: "PATCH", body: JSON.stringify({ is_archived: true }) }));
  fireEvent.click(screen.getByRole("tab", { name: "Archived" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/procurement/makerspace/7/vendors?archived=1"));
});
