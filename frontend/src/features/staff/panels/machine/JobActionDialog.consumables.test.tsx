import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobActionDialog } from "./JobActionDialog";
import type { StaffJob } from "./machineJobsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const profileRow = (key: string, name: string, required: boolean, unit = "sheet") => ({ id: key.length, machine_type: 7, key, name, kind: "material", unit, attributes: {}, required,
  estimate_by: "staff", record_by: ["staff"], unit_price: null, consumable_pool: null, product: null, position: 0, is_active: true });
const job = { id: 11, title: "Coasters", status: "in_progress", estimated_minutes: 30, pickup_location: "" } as unknown as StaffJob;
const show = (action: "complete" | "quote" | "fail", missing: string[]) => {
  staffRequest.mockImplementation(async (path: string, init?: RequestInit) => path.endsWith("/consumables")
    ? { profile: [profileRow("acrylic", "Acrylic", true), profileRow("tape", "Tape", false, "m")], estimates: [], actuals: [], missing_required: missing } : init?.method === "POST" ? job : {});
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <JobActionDialog job={job} action={action} makerspaceId={1} typeId={7} machines={[]} pools={() => []} unitLabel="minutes" hasPool={false} printer={false} onClose={() => undefined} />
  </QueryClientProvider>);
};
const post = () => staffRequest.mock.calls.find(([path, init]) => init?.method === "POST" && String(path).includes("/machine-service/requests/"));

describe("JobActionDialog consumables", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("blocks completing until the required consumable is recorded, then sends profile_consumptions", async () => {
    show("complete", ["acrylic"]);
    const submit = await screen.findByRole("button", { name: "Complete job" });
    await screen.findByText("Acrylic");
    expect(submit).toBeDisabled();
    expect(screen.getByText("Record Acrylic before completing.")).toBeVisible();
    fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "2" } });
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);
    await waitFor(() => expect(post()).toBeTruthy());
    expect(post()![0]).toBe("/admin/machine-service/requests/11/complete");
    expect(JSON.parse(post()![1].body).profile_consumptions).toEqual([{ key: "acrylic", quantity: "2", attributes: {} }]);
  });

  it("does not block completing when the required amount was already recorded", async () => {
    show("complete", []);
    await screen.findByText("Acrylic");
    expect(screen.getByRole("button", { name: "Complete job" })).toBeEnabled();
  });

  it("rejects a fractional sheet count and sends estimates with a quote", async () => {
    show("quote", []);
    await screen.findByText("Acrylic");
    fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "1.5" } });
    expect(screen.getAllByText("Acrylic is counted in whole numbers.").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Send quote" })).toBeDisabled();
    fireEvent.change(screen.getAllByRole("spinbutton")[0], { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Send quote" }));
    await waitFor(() => expect(post()).toBeTruthy());
    expect(JSON.parse(post()![1].body).consumable_estimates).toEqual([{ key: "acrylic", quantity: "3", attributes: {} }]);
  });
});
