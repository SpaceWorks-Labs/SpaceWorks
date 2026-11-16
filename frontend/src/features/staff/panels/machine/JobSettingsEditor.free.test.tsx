import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { JobSettingsEditor } from "./JobSettingsEditor";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));
const settings = { accepts_job_requests: true, quote_mode: "auto", quote_above_amount: null, payment_timing: "completion",
  member_fault_charge: "none", max_open_jobs: null, max_job_minutes: null, runs_unattended: null, file_groups: [] };

describe("JobSettingsEditor in a free machines domain (#184 G3)", () => {
  it("hides quote, payment-timing and failure-charge fields and says why", async () => {
    staffRequest.mockResolvedValue(settings);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["staff", "makerspaces"], [{ id: 1, enabled_modules: ["machines"], enabled_features: ["charges.enabled"] }]);
    render(<QueryClientProvider client={client}><JobSettingsEditor makerspaceId={1} machineTypeId={7} /></QueryClientProvider>);
    expect(await screen.findByText(/Machine charges are off in this space/)).toBeVisible();
    expect(screen.queryByLabelText("Quotes")).toBeNull();
    expect(screen.queryByLabelText("When members pay")).toBeNull();
    expect(screen.getByLabelText(/Open jobs per member/)).toBeVisible();
  });
});
