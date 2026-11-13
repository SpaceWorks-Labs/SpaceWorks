import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Makerspace } from "../panels/shared";
import { MaintenanceView } from "./MaintenanceView";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));
vi.mock("./subjectsApi", () => ({ useSubjectOptions: () => ({ options: [], loading: false }) }));
vi.mock("../panels/machine/MaintenanceFeedControl", () => ({ MaintenanceFeedControl: () => <p>Maintenance calendar control</p> }));

const schedule = (patch = {}) => ({ id: 5, subject_type: "inventory_product", subject_id: 3, subject_label: "Drill press",
  description: "Oil the column", interval_days: 30, next_due: "2099-01-10", is_active: true, ...patch });
const show = (manager: boolean) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MaintenanceView makerspace={{ id: 4 } as Makerspace} manager={manager} /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("MaintenanceView schedule edit", () => {
  it("edits an item schedule with PATCH subject-maintenance", async () => {
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method
      ? schedule({ interval_days: 14 }) : { machine_schedules: [], schedules: [schedule()] }));
    show(true);
    fireEvent.click(await screen.findByRole("button", { name: "Edit schedule: Oil the column" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Every (days)"), { target: { value: "14" } });
    fireEvent.click(within(dialog).getByLabelText("Active (untick to pause)"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Save schedule" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/subject-maintenance/5", { method: "PATCH",
      body: JSON.stringify({ description: "Oil the column", interval_days: 14, next_due: "2099-01-10", is_active: false }) }));
  });

  it("shows paused schedules to managers only, and no Edit to technicians", async () => {
    staffRequest.mockResolvedValue({ machine_schedules: [], schedules: [schedule(), schedule({ id: 6, description: "Belt check", is_active: false })] });
    const { unmount } = show(true);
    expect(await screen.findByText("Belt check")).toBeInTheDocument();
    expect(screen.getByText("Paused")).toBeInTheDocument();
    unmount();
    show(false);
    expect(await screen.findByText("Oil the column")).toBeInTheDocument();
    expect(screen.queryByText("Belt check")).toBeNull();
    expect(screen.queryByRole("button", { name: /Edit schedule/ })).toBeNull();
  });
});

describe("MaintenanceView calendar feed (decision 220(d)3)", () => {
  const due = { id: 8, machine_id: 2, machine_name: "Laser A", description: "Align mirrors", next_due: "2099-01-10" };
  const render220 = (features: string[]) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MaintenanceView makerspace={{ id: 4, enabled_features: features } as Makerspace} manager={false} /></QueryClientProvider>);

  it("offers a covering technician the feed for the machines they cover", async () => {
    staffRequest.mockResolvedValue({ machine_schedules: [due], schedules: [] });
    render220(["maintenance.calendar_feed"]);
    expect(await screen.findByText("Maintenance calendar control")).toBeInTheDocument();
  });

  it("hides it with the feed switched off or no covered machines", async () => {
    staffRequest.mockResolvedValue({ machine_schedules: [due], schedules: [] });
    const { unmount } = render220([]);
    expect(await screen.findByText("Align mirrors")).toBeInTheDocument();
    expect(screen.queryByText("Maintenance calendar control")).toBeNull();
    unmount();
    staffRequest.mockResolvedValue({ machine_schedules: [], schedules: [schedule()] });
    render220(["maintenance.calendar_feed"]);
    expect(await screen.findByText("Oil the column")).toBeInTheDocument();
    expect(screen.queryByText("Maintenance calendar control")).toBeNull();
  });
});
