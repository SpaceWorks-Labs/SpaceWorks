import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MachineType } from "../../machinesApi";
import { MachineServiceConsole } from "./MachineServiceConsole";
import { blankServiceDraft } from "./serviceDrafts";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const machineType: MachineType = {
  id: 7, slug: "laser", name: "Laser cutters", icon: "", is_builtin: false, managing_action: "manage_machines",
  makerspace: 1, capability_config: { metering_unit: "length", requires_booking: false },
};

function renderConsole(draft = blankServiceDraft(), logging = false) {
  staffRequest.mockImplementation(async (path?: string) =>
    path?.includes("machine-service/requests") ? [{ id: 4, title: "Laser job", status: "pending", planned_quantity: "20", actual_consumed_quantity: "0" }] : []);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <MachineServiceConsole makerspaceId={1} canManage machineType={machineType} machines={[]} pools={[]} draft={draft}
      setDraft={vi.fn()} logging={logging} onLogging={vi.fn()} />
  </QueryClientProvider>);
}

describe("service console on small screens", () => {
  it("keeps the job action's confirm row pinned and opens the number pad for quantities", async () => {
    renderConsole({ ...blankServiceDraft(), action: { id: 4, name: "accept" } });
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Confirm" });
    expect(confirm.parentElement).toHaveClass("sticky", "bottom-0", "flex-wrap");
    expect(within(dialog).getByLabelText("Estimated minutes")).toHaveAttribute("inputmode", "decimal");
    // A modal is ~32rem wide: fields pair up from `sm`, never three or four abreast.
    expect(within(dialog).getByLabelText("Estimated minutes").closest(".grid.gap-2")).toHaveClass("sm:grid-cols-2");
  });

  it("lays the manual usage form out in two columns inside its dialog", async () => {
    renderConsole(blankServiceDraft(), true);
    const dialog = await screen.findByRole("dialog", { name: "Log usage" });
    const form = within(dialog).getByLabelText("Manual usage machine").parentElement!;
    expect(form).toHaveClass("sm:grid-cols-2");
    expect(form).not.toHaveClass("md:grid-cols-4");
  });
});
