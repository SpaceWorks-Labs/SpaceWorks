import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Machine } from "../../machinesApi";
import { OverviewTab } from "./OverviewTab";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));
vi.mock("../../ImageUploader", () => ({ ImageUploader: () => null }));
vi.mock("../MachinePublicSettings", () => ({ MachinePublicSettings: () => null }));
vi.mock("../../pricing/PriceOverrideCard", () => ({ PriceOverrideCard: () => null }));

const machine = { id: 4, name: "Laser A", location: "", notes: "", firmware_version: "", camera_feed_url: "", status: "idle",
  usage_hours: "3", is_active: true, image_url: null, machine_type: { id: 7, name: "Laser cutters" } } as unknown as Machine;

describe("set status with downtime details", () => {
  it("asks for a reason and expected-back time when taking a machine down", async () => {
    staffRequest.mockResolvedValue(machine);
    render(<QueryClientProvider client={new QueryClient()}><OverviewTab machine={machine} makerspaceId={1} canManageMachines={false}
      canEdit={false} canOperate canRetire={false} canUnretire={false} /></QueryClientProvider>);
    expect(screen.queryByLabelText(/Expected back/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Machine status"), { target: { value: "offline" } });
    fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Tube cracked" } });
    fireEvent.click(screen.getByRole("button", { name: "Set status" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machines/4/set-status",
      { method: "POST", body: JSON.stringify({ status: "offline", reason: "Tube cracked" }) }));
  });
});
