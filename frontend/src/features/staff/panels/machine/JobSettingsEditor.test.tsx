import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobSettingsEditor } from "./JobSettingsEditor";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const settings = { accepts_job_requests: true, quote_mode: "auto", quote_above_amount: null, payment_timing: "completion",
  member_fault_charge: "none", max_open_jobs: null, max_job_minutes: null, runs_unattended: null, file_groups: [] };
const path = "/admin/makerspaces/1/machine-types/7/job-settings";
const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <JobSettingsEditor makerspaceId={1} machineTypeId={7} /></QueryClientProvider>);

describe("JobSettingsEditor", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("edits and saves the per-type job settings", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "PUT" ? JSON.parse(String(init.body)) : settings);
    show();
    fireEvent.change(await screen.findByLabelText("Quotes"), { target: { value: "above" } });
    fireEvent.change(screen.getByLabelText("Quote above this amount"), { target: { value: "250" } });
    fireEvent.change(screen.getByLabelText("When members pay"), { target: { value: "prepay" } });
    fireEvent.change(screen.getByLabelText(/Open jobs per member/), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "3D printing" }));
    fireEvent.click(screen.getByRole("button", { name: "Save job settings" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(path, expect.objectContaining({ method: "PUT" })));
    const body = JSON.parse(staffRequest.mock.calls.find(([, init]) => init?.method === "PUT")![1].body);
    expect(body).toMatchObject({ quote_mode: "above", quote_above_amount: "250", payment_timing: "prepay", max_open_jobs: 3, file_groups: ["fab-3dprint"] });
    expect(await screen.findByText("Job settings saved.")).toBeVisible();
  });

  it("turns read-only with the reason when the setting is not delegated", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => {
      if (init?.method === "PUT") throw Object.assign(new Error("Forbidden"), { code: "setting_not_delegated", status: 403 });
      return settings;
    });
    show();
    fireEvent.change(await screen.findByLabelText("When members pay"), { target: { value: "prepay" } });
    fireEvent.click(screen.getByRole("button", { name: "Save job settings" }));
    expect(await screen.findByText(/Only the Space Manager/)).toBeVisible();
    expect(screen.getByLabelText("When members pay")).toBeDisabled();
    expect(screen.getByLabelText("When members pay")).toHaveValue("completion");
    expect(screen.queryByRole("button", { name: "Save job settings" })).not.toBeInTheDocument();
  });
});
