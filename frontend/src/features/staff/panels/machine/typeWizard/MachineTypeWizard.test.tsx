import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MachineTypeWizard } from "./MachineTypeWizard";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async importOriginal => ({ ...(await importOriginal<object>()), staffRequest }));

const spec = { version: 1, basics: { metering_unit: "minutes", requires_booking: false, is_public: true },
  consumables: [{ key: "acrylic_sheet", name: "Acrylic sheet" }], intake_fields: [], pricing: { charge_by: "time" }, access: { open_to_all_members: false, supervised: true },
  bookings: { bookable: false }, safety: {}, maintenance: [{ title: "Clean the lens", trigger: "days", interval: 14 }], job: { accepts_job_requests: true, runs_unattended: false },
  notifications: { job_finished: true, job_failed: true, low_stock: false }, documents: { training_notes: "Wear eye protection." } };
const template = { id: null, key: "laser_cutter", name: "Laser cutter", description: "Cuts sheets", category: "Fabrication", icon: "zap", spec, is_builtin: true, customised: false, based_on: null, is_active: true };
const type = { id: 9, slug: "laser-cutter", name: "Laser cutter", icon: "zap", is_builtin: false, managing_action: "", makerspace: 1, capability_config: { metering_unit: "minutes", requires_booking: false } };
const row = { id: 1, machine_type: 9, key: "acrylic_sheet", name: "Acrylic sheet", kind: "material", unit: "sheet", attributes: { colour: ["Clear"] }, required: true, estimate_by: "member",
  record_by: ["staff"], unit_price: "2.50", consumable_pool: null, product: null, position: 0, is_active: true, in_use: false };
const applied = { machine_type_id: 9, created_type: true, template_key: "laser_cutter", consumables_added: ["acrylic_sheet"], consumables_skipped: [],
  prefill: { pricing: spec.pricing, access: spec.access, bookings: spec.bookings, safety: spec.safety, maintenance: spec.maintenance, job: spec.job, notifications: spec.notifications, documents: spec.documents } };

function route(path: string, init?: RequestInit) {
  const method = init?.method ?? "GET";
  if (path.endsWith("/machine-type-templates")) return [template];
  if (path.endsWith("/apply")) return applied;
  if (path.endsWith("/machine-types") && method === "POST") return type;
  if (path.endsWith("/machine-types")) return { results: [type] };
  if (path.endsWith("/consumables")) return [row];
  if (path.includes("/consumable-stock")) return { pools: [], products: [] };
  if (path.includes("/machine-types/9") && method === "PATCH") return type;
  return {};
}
const show = (props: Partial<Parameters<typeof MachineTypeWizard>[0]> = {}) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MachineTypeWizard makerspaceId={1} onClose={() => undefined} {...props} /></QueryClientProvider>);
const calls = (method: string, suffix: string) => staffRequest.mock.calls.filter(([path, init]) => (init?.method ?? "GET") === method && String(path).endsWith(suffix));

describe("MachineTypeWizard", () => {
  beforeEach(() => { staffRequest.mockReset(); staffRequest.mockImplementation(async (path: string, init?: RequestInit) => route(path, init)); });

  it("applies a template and shows its consumables on the next step", async () => {
    show();
    fireEvent.click(await screen.findByRole("radio", { name: /Laser cutter/ }));
    fireEvent.click(screen.getByRole("button", { name: /Next: Basics/ }));
    expect(screen.getByLabelText("Name")).toHaveValue("Laser cutter");
    fireEvent.click(screen.getByRole("button", { name: "Create type and continue" }));
    await waitFor(() => expect(calls("POST", "/laser_cutter/apply")).toHaveLength(1));
    expect(JSON.parse(calls("POST", "/laser_cutter/apply")[0][1].body)).toEqual({ name: "Laser cutter", slug: "laser-cutter" });
    expect(await screen.findByText("Acrylic sheet")).toBeVisible();
    expect(screen.getByText("Required")).toBeVisible();
  });

  it("starts blank without calling apply", async () => {
    show();
    fireEvent.click(await screen.findByRole("radio", { name: /Start blank/ }));
    fireEvent.click(screen.getByRole("button", { name: /Next: Basics/ }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Vinyl plotter" } });
    expect(screen.getByLabelText("Slug")).toHaveValue("vinyl-plotter");
    fireEvent.click(screen.getByRole("button", { name: "Create type and continue" }));
    await waitFor(() => expect(calls("POST", "/machine-types")).toHaveLength(1));
    expect(JSON.parse(calls("POST", "/machine-types")[0][1].body)).toMatchObject({ slug: "vinyl-plotter", name: "Vinyl plotter", capability_config: { metering_unit: "minutes" } });
    expect(calls("POST", "/apply")).toHaveLength(0);
  });

  it("opens an existing type on Basics and lets every step be reached", async () => {
    show({ machineType: type as never });
    expect(screen.getByLabelText("Name")).toHaveValue("Laser cutter");
    expect(screen.getByLabelText(/^Slug/)).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Laser cutter 60W" } });
    fireEvent.click(screen.getByRole("button", { name: "Save basics" }));
    await waitFor(() => expect(calls("PATCH", "/machine-types/9")).toHaveLength(1));
    expect(JSON.parse(calls("PATCH", "/machine-types/9")[0][1].body)).toMatchObject({ name: "Laser cutter 60W" });
    fireEvent.change(screen.getByLabelText("Go to step"), { target: { value: "consumables" } });
    expect(await screen.findByText("Acrylic sheet")).toBeVisible();
    const options = within(screen.getByLabelText("Go to step")).getAllByRole("option");
    expect(options).toHaveLength(12);
    options.forEach(option => expect(option).not.toBeDisabled());
  });
});
