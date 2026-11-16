import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api/errors";
import { BulkLimitsApply } from "./BulkLimitsApply";
import { SpaceLimitsSection } from "./SpaceLimitsSection";
import { limitsSpaceId } from "./PlatformLimitsPage";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

const DATA = {
  custom_domain: false, hosted: true, hosting_type: "hosted", hosting_active: true,
  areas: [{ key: "people", label: "People" }, { key: "events", label: "Events" }, { key: "messaging", label: "Messaging" },
    { key: "integrations", label: "Integrations" }, { key: "storage", label: "Storage" }],
  rows: [
    { key: "members", label: "members", unit: "count", area: "people", effective: 40, source: "override", override: 40, has_override: true, used: 36, suggested: null },
    { key: "storage", label: "storage", unit: "bytes", area: "storage", effective: null, source: "unlimited", override: null, has_override: false, used: 3 * 1024 ** 3, suggested: null },
  ],
  quota_rows: [{ key: "events_monthly", label: "events created this month", unit: "count", area: "events", limit: 5, used: 5, percent: 100, level: "limit" }],
  platform_rows: [
    { key: "platform_sms_monthly", label: "sms", unit: "count", area: "messaging", limit: null, used: 12, percent: null },
    { key: "api_requests_per_minute", label: "API requests per minute", unit: "per_minute", area: "integrations", limit: 600, used: null, percent: null },
  ],
};
const mount = (ui: React.ReactElement) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
const puts = () => staffRequest.mock.calls.filter(([, init]) => init?.method === "PUT").map(([path, init]) => [path, JSON.parse(init.body)]);

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue(DATA); });

describe("superadmin limits by area (decisions 281, 284)", () => {
  it("groups every row from the payload under its area, in the server's order, with usage and levels", async () => {
    mount(<SpaceLimitsSection makerspaceId={7} headingLevel={2} />);
    await screen.findByRole("heading", { name: "People" });
    expect(screen.getAllByRole("heading", { level: 3 }).map(h => h.textContent)).toEqual(["People", "Events", "Messaging", "Integrations", "Storage"]);
    const events = screen.getByRole("heading", { name: "Events" }).closest("section")!;
    expect(within(events).getByText("At limit")).toBeInTheDocument();
    expect(within(events).getByRole("progressbar", { name: "New events this month used" })).toHaveAttribute("aria-valuenow", "100");
    expect(within(screen.getByRole("heading", { name: "People" }).closest("section")!).getByText("Near limit")).toBeInTheDocument();
    expect(screen.getByText(/Using 3 GB · no limit/)).toBeInTheDocument();
    expect(screen.getByText(/Limit: 600 a minute/)).toBeInTheDocument();
    expect(screen.getByLabelText("Limit for this space: Texts through the platform this month")).toHaveAttribute("placeholder", "No limit");
  });

  it("saves the complete override map, keeping stored values and converting MB to bytes", async () => {
    mount(<SpaceLimitsSection makerspaceId={7} />);
    const sms = await screen.findByLabelText("Limit for this space: Texts through the platform this month");
    fireEvent.change(sms, { target: { value: "200" } });
    fireEvent.change(screen.getByLabelText(/Limit for this space: Storage/), { target: { value: "1024" } });
    fireEvent.click(screen.getByRole("button", { name: "Save limits" }));
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(puts()[0]).toEqual(["/admin/platform/spaces/7/limits", { overrides: {
      events_monthly: 5, platform_sms_monthly: 200, api_requests_per_minute: 600, members: 40, storage: 1024 * 1048576 } }]);
  });

  it("resets every limit to none in one go", async () => {
    mount(<SpaceLimitsSection makerspaceId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: "Reset every limit to none" }));
    fireEvent.click(screen.getByRole("button", { name: "Save limits" }));
    await waitFor(() => expect(puts()[0]).toEqual(["/admin/platform/spaces/7/limits", { overrides: {} }]));
  });

  it("keeps Save off until something changed and refuses a non-number", async () => {
    mount(<SpaceLimitsSection makerspaceId={7} />);
    const save = await screen.findByRole("button", { name: "Save limits" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Limit for this space: Members"), { target: { value: "lots" } });
    expect(save).toBeDisabled();
  });

  it("knows the limits page path and the inbox notice path", () => {
    expect(limitsSpaceId("/admin/platform-limits/12")).toBe(12);
    expect(limitsSpaceId("/admin/platform/spaces/9/limits")).toBe(9);
    expect(limitsSpaceId("/admin/platform-limits")).toBeNull();
  });
});

describe("bulk limits (decision 284)", () => {
  const spaces = [{ id: 7, name: "North Lab" }, { id: 8, name: "South Lab" }];

  it("sets and clears the chosen keys on the chosen spaces", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "POST" ? { updated: 2, makerspace_ids: [7, 8] } : DATA);
    mount(<BulkLimitsApply spaces={spaces} />);
    fireEvent.click(screen.getByRole("button", { name: "Set limits on several spaces" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select all 2" }));
    const first = await screen.findByRole("combobox", { name: "Limit 1" });
    await waitFor(() => expect(within(first).getByRole("option", { name: "New events this month" })).toBeInTheDocument());
    fireEvent.change(first, { target: { value: "events_monthly" } });
    fireEvent.change(screen.getByRole("textbox", { name: "New value 1" }), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Add another limit" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Limit 2" }), { target: { value: "members" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to 2 spaces" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/spaces/limits-bulk",
      { method: "POST", body: JSON.stringify({ makerspace_ids: [7, 8], set: { events_monthly: 10 }, clear: ["members"] }) }, "platform"));
    expect(await screen.findByText("Limits changed on 2 spaces.")).toBeInTheDocument();
  });

  it("names the refused space when the all-or-nothing batch fails", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => {
      if (init?.method === "POST") throw new StructuredApiError(409, { code: "bulk_failed", failed_id: 8, cause: "Unknown makerspace." });
      return DATA;
    });
    mount(<BulkLimitsApply spaces={spaces} />);
    fireEvent.click(screen.getByRole("button", { name: "Set limits on several spaces" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "South Lab" }));
    const first = await screen.findByRole("combobox", { name: "Limit 1" });
    await waitFor(() => expect(within(first).getAllByRole("option").length).toBeGreaterThan(1));
    fireEvent.change(first, { target: { value: "members" } });
    fireEvent.change(screen.getByRole("textbox", { name: "New value 1" }), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to 1 space" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No limits changed. South Lab was refused: Unknown makerspace.");
  });
});
