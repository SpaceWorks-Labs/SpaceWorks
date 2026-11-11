import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { MachinesPanel } from "./MachinesPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

it("preserves owned type and shared-pool drafts while inactive settings DOM is removed", async () => {
  staffRequest.mockImplementation(async (path: string) => {
    if (path.endsWith("/machine-types")) return [{ id: 1, name: "Laser cutters", slug: "laser", is_builtin: true,
      makerspace: null, can_create_machine: false, capability_config: { metering_unit: "length", requires_booking: false } }];
    if (path.endsWith("/machines")) return { count: 0, results: [], next: null };
    if (path.includes("pricing")) return { currency: "INR", results: [] };
    if (path.endsWith("/policy")) return { cert_reminder_days: null, reminder_lead_days: null, grace_days: null };
    return [];
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<MemoryRouter initialEntries={["/admin/machines"]}><QueryClientProvider client={client}>
    <MachinesPanel makerspaceId={1} canManage canConfigureMachineTypes maintenanceEnabled={false}
      machineServiceEnabled printingEnabled delegatedRecipientRulesEnabled={false} />
  </QueryClientProvider></MemoryRouter>);
  fireEvent.click(await screen.findByRole("link", { name: "Settings" }));
  fireEvent.click(screen.getByText("Machine types and pricing"));
  fireEvent.change(screen.getByPlaceholderText("laser-cutter"), { target: { value: "vinyl-cutter" } });
  fireEvent.change(screen.getByPlaceholderText("Laser cutter"), { target: { value: "Vinyl cutters" } });
  fireEvent.change(screen.getByLabelText("Rate per unit (INR)"), { target: { value: "1.50" } });
  const sharedToggle = screen.getByRole("button", { name: /Shared consumables/ });
  fireEvent.click(sharedToggle);
  const shared = within(sharedToggle.closest("section")!);
  fireEvent.change(shared.getByLabelText("Material"), { target: { value: "Draft acrylic" } });
  fireEvent.change(shared.getByLabelText("Initial quantity"), { target: { value: "250" } });

  fireEvent.click(screen.getByRole("link", { name: "Machines 0" }));
  expect(screen.queryByPlaceholderText("laser-cutter")).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue("Draft acrylic")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1, name: "Machines" })).toBeVisible();

  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  fireEvent.click(screen.getByText("Machine types and pricing"));
  expect(screen.getByPlaceholderText("laser-cutter")).toHaveValue("vinyl-cutter");
  expect(screen.getByPlaceholderText("Laser cutter")).toHaveValue("Vinyl cutters");
  expect(screen.getByLabelText("Rate per unit (INR)")).toHaveValue(1.5);
  expect(screen.getByDisplayValue("Draft acrylic")).toBeVisible();
  expect(screen.getByDisplayValue("250")).toBeVisible();
});
