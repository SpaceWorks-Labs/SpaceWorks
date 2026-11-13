import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HealthCardView } from "./HealthCardView";
import { HostingTypeControl } from "./HostingTypeControl";
import { SpaceLimitsSection } from "./SpaceLimitsSection";
import type { HealthCard } from "./spacesApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

const mount = (ui: React.ReactElement) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}>{ui}</QueryClientProvider>);

const card = (overrides: Partial<HealthCard> = {}): HealthCard => ({
  id: 7, name: "North Lab", slug: "north-lab", public_code: "NL", state: "active", created_at: "2026-01-01T00:00:00Z",
  lifecycle_state: "active", archived_at: null, suspended: null, read_only: null, schedule: null,
  usage: { managed: true, resources: [{ key: "members", label: "members", used: 9, limit: 10, unit: "count", percent: 90 }] },
  usage_peak_percent: 90, last_activity_at: null, backups: { last_backed_up_at: null, last_drill: null },
  security: { blocked_accounts: 0, locked_settings: 0 }, open_issues: 0, modules: [], managers: [],
  hosting_type: "hosted", hosted: true, ...overrides,
});

beforeEach(() => { staffRequest.mockReset(); });

describe("hosting type (decision 236)", () => {
  it("marks a space as hosted through the audited PUT", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "PUT"
      ? { hosting_type: "hosted", hosting_active: true, hosted: true } : { hosting_type: "own", hosting_active: true, hosted: false });
    mount(<HostingTypeControl makerspaceId={7} />);
    expect(await screen.findByText(/no plan, no limits, no hosting bills/)).toBeVisible();
    fireEvent.click(screen.getByRole("radio", { name: /Hosted space/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/spaces/7/hosting-type",
      { method: "PUT", body: JSON.stringify({ hosting_type: "hosted" }) }, "platform"));
  });

  it("is disabled with a hint while hosting is off", async () => {
    staffRequest.mockResolvedValue({ hosting_type: "hosted", hosting_active: false, hosted: false });
    mount(<HostingTypeControl makerspaceId={7} />);
    expect(await screen.findByText(/Turn on "Host other makerspaces"/)).toBeVisible();
    for (const radio of screen.getAllByRole("radio")) expect(radio).toBeDisabled();
  });

  it("shows a badge and the closest limit for a hosted space", () => {
    mount(<HealthCardView card={card()} managedPlans onOpen={vi.fn()} onDetails={vi.fn()} />);
    expect(screen.getByText("Hosted space")).toBeVisible();
    expect(screen.getByText("Highest usage: Members")).toBeVisible();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("shows Unlimited (own space) and no meter for an own space", () => {
    mount(<HealthCardView card={card({ hosting_type: "own", hosted: false, usage_peak_percent: null })} managedPlans onOpen={vi.fn()} onDetails={vi.fn()} />);
    expect(screen.getByText("Own space")).toBeVisible();
    expect(screen.getByText("Unlimited (own space)")).toBeVisible();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("explains that an own space has no limits instead of the limits form", async () => {
    staffRequest.mockResolvedValue({ custom_domain: false, hosted: false, hosting_type: "own", hosting_active: true, rows: [] });
    mount(<SpaceLimitsSection makerspaceId={7} />);
    expect(await screen.findByText(/Unlimited \(own space\)/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Save limits" })).not.toBeInTheDocument();
  });

  it("clears a limit back to unlimited", async () => {
    const data = { custom_domain: false, hosted: true, rows: [{ key: "members", label: "members", unit: "count", effective: 5,
      source: "override", override: 5, has_override: true, used: 1, suggested: 25 }] };
    staffRequest.mockResolvedValue(data);
    mount(<SpaceLimitsSection makerspaceId={7} />);
    fireEvent.click(await screen.findByRole("button", { name: "Reset to none: Members" }));
    expect(screen.getByLabelText("Limit for this space: Members")).toHaveValue("");
    expect(screen.getByText("Suggested: 25")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Save limits" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/spaces/7/limits",
      { method: "PUT", body: JSON.stringify({ overrides: {} }) }, "platform"));
  });
});
