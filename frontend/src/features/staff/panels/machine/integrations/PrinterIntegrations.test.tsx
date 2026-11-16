import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Machine } from "../../../machinesApi";
import { PrinterBindingsSection } from "./PrinterBindingsSection";
import { TypeIntegrationSection } from "./TypeIntegrationSection";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../../../lib/api")), staffRequest }));

const machines = [{ id: 21, name: "Prusa A" }, { id: 22, name: "Prusa B" }] as Machine[];
const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const binding = { id: "b-1", makerspace: 4, device: "d-1", machine: 21, enabled: true, auto_apply_terminal: false, created_at: "", updated_at: "" };
const job = { id: "j-1", device: "d-1", machine: 21, service_request: 90, machine_name: "Prusa A", service_request_name: "Request 90",
  external_job_id: "benchy.gcode", state: "reported", telemetry_state: "idle", progress_percent: 100, outcome: "completed",
  actual_minutes: 42, failure_reason: "", percent_complete: null, actual_grams: "12.50", actual_quantity: null,
  reported_at: "", applied_at: null, created_at: "", consumptions: [] };
const devices = page([{ id: "d-1", name: "Bench printer", kind: "printer", status: "active" },
  { id: "d-2", name: "Spare printer", kind: "printer", status: "active" }, { id: "d-3", name: "Labeller", kind: "label_printer", status: "active" }]);
const board = { lanes: [{ machine_id: 21, machine_name: "Prusa A", status: "running", locked_out: false,
  running: [{ id: 90, title: "Benchy" }], assigned: [] }], queue: [], review: [], waiting_on_member: [], ready: [],
  overdue_pickup_ids: [], no_show_member_ids: [] };

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  {node}</QueryClientProvider>);

function respond(path: string, init?: RequestInit) {
  if (init?.method === "POST" && path.endsWith("/apply")) return { ...job, state: "applied" };
  if (init?.method === "POST" && path.endsWith("/printer-jobs")) return { ...job, id: "j-2", state: "awaiting" };
  if (init?.method) return binding;
  if (path.includes("/device-printer-bindings")) return page([binding, { ...binding, id: "b-x", machine: 99 }]);
  if (path.includes("/devices")) return devices;
  if (path.includes("/printer-jobs/")) return job;
  if (path.includes("/printer-jobs")) return page([job]);
  if (path.includes("/machine-service/board")) return board;
  return [];
}

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(respond(path, init))); });

describe("PrinterBindingsSection", () => {
  it("lists only this type's connections and toggles, connects and disconnects", async () => {
    wrap(<PrinterBindingsSection makerspaceId={4} machineTypeId={8} machines={machines} />);
    const list = await screen.findByRole("list", { name: "Connected printers" });
    expect(await within(list).findByText("Bench printer")).toBeInTheDocument();
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(within(list).getByLabelText("Apply results automatically"));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/device-printer-bindings/b-1",
      { method: "PATCH", body: JSON.stringify({ auto_apply_terminal: true }) }));

    const device = screen.getByLabelText("Printer device");
    expect(within(device).queryByText("Labeller")).toBeNull();
    fireEvent.change(device, { target: { value: "d-2" } });
    fireEvent.change(screen.getByLabelText("Machine"), { target: { value: "22" } });
    fireEvent.click(screen.getByRole("button", { name: "Connect printer" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/4/device-printer-bindings", { method: "POST",
      body: JSON.stringify({ device_id: "d-2", machine_id: 22, enabled: true, auto_apply_terminal: false }) }));

    fireEvent.click(within(list).getByRole("button", { name: "Disconnect" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Disconnect" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/device-printer-bindings/b-1", { method: "DELETE" }));
  });

  it("sends the running job to a printer and applies a reported result", async () => {
    wrap(<PrinterBindingsSection makerspaceId={4} machineTypeId={8} machines={machines} />);
    const jobs = await screen.findByRole("list", { name: "Printer jobs" });
    expect(await within(jobs).findByText("Result reported")).toBeInTheDocument();
    fireEvent.click(within(jobs).getByRole("button", { name: "Details" }));
    expect(await within(jobs).findByText("12.50")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/printer-jobs/j-1");
    fireEvent.click(within(jobs).getByRole("button", { name: "Apply result" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/printer-jobs/j-1/apply", { method: "POST", body: "{}" }));

    fireEvent.change(screen.getByLabelText("Printer"), { target: { value: "b-1" } });
    const running = screen.getByLabelText("Running job");
    expect(await within(running).findByText("Benchy")).toBeInTheDocument();
    fireEvent.change(running, { target: { value: "90" } });
    fireEvent.change(screen.getByLabelText("Printer job name"), { target: { value: "benchy-2.gcode" } });
    fireEvent.click(screen.getByRole("button", { name: "Send to printer" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/4/printer-jobs", { method: "POST",
      body: JSON.stringify({ binding_id: "b-1", service_request_id: 90, external_job_id: "benchy-2.gcode" }) }));
  });
});

describe("TypeIntegrationSection", () => {
  it("adds the printer agent when none is bound", async () => {
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method ? {} : []));
    wrap(<TypeIntegrationSection makerspaceId={4} machineTypeId={8} />);
    fireEvent.click(await screen.findByRole("button", { name: "Add printer agent" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/4/machine-types/8/integrations",
      { method: "POST", body: JSON.stringify({ kind: "printer_agent" }) }));
  });

  it("switches an integration off and shows live printer status while on", async () => {
    const row = { id: "i-1", makerspace: 4, machine_type: 8, kind: "printer_agent", enabled: true, config_schema_version: 1, created_at: "", updated_at: "" };
    const status = [{ device_id: "d-1", device_name: "Bench printer", machine_id: 21, machine_name: "Prusa A", last_seen_at: null,
      snapshot: { state: "printing", progress_percent: 40, layer_current: 10, layer_total: 50, nozzle_temp_c: "215.0", bed_temp_c: "60.0",
        chamber_temp_c: null, spools: [{ slot: 0, material: "PLA", colour: "red", remaining_percent: 70 }], observed_at: "" } }];
    staffRequest.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(init?.method ? { ...row, enabled: false }
      : path.endsWith("/integration-status") ? status : [row]));
    wrap(<TypeIntegrationSection makerspaceId={4} machineTypeId={8} />);
    expect(await screen.findByText("Printing")).toBeInTheDocument();
    expect(screen.getByText(/Nozzle 215.0 °C/)).toBeInTheDocument();
    expect(screen.getByText(/#0 PLA red 70%/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Switched on"));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-type-integrations/i-1",
      { method: "PATCH", body: JSON.stringify({ enabled: false }) }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-type-integrations/i-1", { method: "DELETE" }));
  });
});
