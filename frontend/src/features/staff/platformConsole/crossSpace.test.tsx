import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api/errors";
import { PlatformInboxPage } from "./PlatformInboxPage";
import { PlatformQueuesTable } from "./PlatformQueuesTable";
import { PlatformSearch } from "./PlatformSearch";
import { SpaceSnapshotSection } from "../platformSpaces/SpaceSnapshotSection";
import { BulkPlanAssign } from "../platformSpaces/BulkPlanAssign";
import type { HealthCard } from "../platformSpaces/spacesApi";

const { staffRequest, openSpaceTab } = vi.hoisted(() => ({ staffRequest: vi.fn(), openSpaceTab: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest }));
vi.mock("./openSpaceTab", () => ({ openSpaceTab }));

const mount = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter>{node}</MemoryRouter></QueryClientProvider>);
const zero = { pending_requests: 0, awaiting_issue: 0, overdue_loans: 0, pending_bookings: 0, pending_registrations: 0, refund_cases_open: 0,
  paid_claims_open: 0, open_incidents: 0, critical_incidents: 0, open_booking_issues: 0, shop_orders_waiting: 0, pending_payments: 0 };

beforeEach(() => { staffRequest.mockReset(); openSpaceTab.mockReset(); });

describe("decision 242(l): superadmin cross-space views", () => {
  it("lists busy spaces first, combines approvals, and opens a space on the platform session", async () => {
    staffRequest.mockResolvedValue({ spaces: [
      { id: 1, name: "Quiet", slug: "quiet", counts: zero, total: 0 },
      { id: 2, name: "Busy", slug: "busy", counts: { ...zero, pending_requests: 2, pending_bookings: 3, critical_incidents: 1 }, total: 6 },
    ] });
    mount(<PlatformQueuesTable />);
    expect(await screen.findByText("Busy")).toBeInTheDocument();
    expect(screen.queryByText("Quiet")).toBeNull();
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/queues", {}, "platform");
    expect(screen.getByRole("cell", { name: "5" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Only spaces with something waiting" }));
    expect(screen.getByText("Quiet")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Busy" }));
    expect(openSpaceTab).toHaveBeenCalledWith(2, "/admin/dashboard");
  });

  it("shows the unread inbox per space and opens that space's inbox", async () => {
    staffRequest.mockResolvedValue({ spaces: [{ id: 3, name: "Forge", personal_unread: 2, notices_unread: 1 }], total: 3 });
    mount(<PlatformInboxPage />);
    expect(await screen.findByText("For you: 2 · Space notices: 1")).toBeInTheDocument();
    expect(screen.getByText("3 unread in total")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open inbox" }));
    expect(openSpaceTab).toHaveBeenCalledWith(3, "/admin/notifications");
  });

  it("searches only from 3 characters and names the space of each hit", async () => {
    staffRequest.mockResolvedValue({ results: [{ kind: "receipt", label: "RCPT-0042", space_id: 3 }, { kind: "person", label: "ada", account_id: 9, space_ids: [] }] });
    mount(<PlatformSearch spaceNames={{ 3: "Forge" }} />);
    const input = screen.getByLabelText(/receipt number/);
    fireEvent.change(input, { target: { value: "rc" } });
    await new Promise(resolve => setTimeout(resolve, 450));
    expect(staffRequest).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "RCPT-0042" } });
    expect(await screen.findByText("RCPT-0042")).toBeInTheDocument();
    expect(staffRequest.mock.calls[0][0]).toBe("/admin/platform/search?q=RCPT-0042");
    expect(screen.getByText(/Receipt · Forge/)).toBeInTheDocument();
    expect(screen.getByText(/No staff or member role in a live space/)).toBeInTheDocument();
  });

  it("always shows usage in the space snapshot, Own spaces included", async () => {
    staffRequest.mockResolvedValue({ id: 4, name: "Own", slug: "own", hosted: false, counts: { ...zero, open_incidents: 2 },
      usage: { resources: [{ key: "members", label: "Members", used: 40, limit: null, unit: "count" }] } });
    mount(<SpaceSnapshotSection makerspaceId={4} />);
    expect(await screen.findByText("Own space (no plan, no limits)")).toBeInTheDocument();
    expect(screen.getByText("Open incidents")).toBeInTheDocument();
    expect(screen.getByText("40 · no limit")).toBeInTheDocument();
  });

  it("assigns a plan to several hosted spaces and names the refused one on a 409", async () => {
    staffRequest.mockImplementation((path: string) => path.endsWith("/hosting-plans") ? Promise.resolve([{ id: 8, name: "Starter", is_active: true }])
      : Promise.reject(new StructuredApiError(409, { detail: "refused", failed_id: 11, cause: "Trial already used." })));
    const card = (id: number, name: string, hosted: boolean) => ({ id, name, hosted, hosting_type: hosted ? "hosted" : "own" }) as unknown as HealthCard;
    mount(<BulkPlanAssign cards={[card(10, "Alpha", true), card(11, "Beta", true), card(12, "Mine", false)]} />);
    fireEvent.click(screen.getByRole("button", { name: "Give several hosted spaces a plan" }));
    expect(screen.queryByRole("checkbox", { name: "Mine" })).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Alpha" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Beta" }));
    await screen.findByRole("option", { name: "Starter" });
    fireEvent.change(screen.getByLabelText("Plan"), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Assign to 2 spaces" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No plans changed. Beta could not take this plan: Trial already used.");
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/spaces/plan-bulk",
      { method: "POST", body: JSON.stringify({ makerspace_ids: [10, 11], plan_id: 8 }) }, "platform"));
  });
});
