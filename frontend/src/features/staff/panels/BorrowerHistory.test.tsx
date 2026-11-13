import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../areaOverview/allowedTabsContext";
import { StaffListContext } from "../StaffListContext";
import { Ledger } from "./Ledger";
import type { LedgerRow } from "./LedgerParts";
import { RequestDetail } from "./RequestDetail";
import type { HardwareRequest } from "./Queues";
import type { Makerspace } from "./shared";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

function wrap(node: ReactNode, actions: string[], path = "/m/lab/admin/ledger") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AllowedTabsContext.Provider value={["requests", "ledger", "payments"]}>
      <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 1, actions }}>{node}</StaffListContext.Provider>
    </AllowedTabsContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}
const ledgerRow: LedgerRow = { source: "request", item_name: "Multimeter", container: null, units: [], target_label: null,
  holder: "Asha", quantity: 1, since: "2026-11-01T10:00:00Z", due: null, makerspace_id: 4, reference_id: 1, status: "issued",
  request_id: 31, product_id: 5, holder_id: 9 };
const activity = { member_id: 9, errors: [], access_status: "restricted", is_member: false,
  areas: [{ area: "lending", count: 2, rows_visible: true, open: 1, rows: [] }, { area: "money", count: 1, rows_visible: true, pending: 1, owed: { INR: "50.00" }, rows: [] }] };

function respond() {
  api.staffRequest.mockImplementation(async (path: string) => path.includes("/members/9/activity") ? activity : { count: 1, results: [ledgerRow] });
}

describe("borrower history drawer (A26)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); });

  it("opens the borrower's loans, charges and restriction state from a ledger row", async () => {
    respond();
    wrap(<Ledger makerspace={{ id: 4, slug: "lab", name: "Lab" } as Makerspace} isSuperadmin={false} />, ["view_inventory"]);
    fireEvent.click(await screen.findByRole("button", { name: "Borrower history" }));
    expect(await screen.findByText("Restricted: cannot borrow until cleared")).toBeVisible();
    expect(screen.getByText("Account only, not a member of this space.")).toBeVisible();
    expect(screen.getByText(/50/)).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/members/9/activity", expect.anything());
  });

  it("is not offered to a handover-only desk", async () => {
    respond();
    wrap(<Ledger makerspace={{ id: 4, slug: "lab", name: "Lab" } as Makerspace} isSuperadmin={false} canExport={false} />, ["issue_request"]);
    await screen.findAllByRole("link", { name: /Multimeter/ });
    expect(screen.queryByRole("button", { name: "Borrower history" })).toBeNull();
  });

  it("expands the borrower history inside a request's detail", async () => {
    respond();
    const request = { id: 31, makerspace_id: 4, requester_id: 9, status: "issued", requester_username: "asha", requested_for: "",
      return_due_at: null, return_reminder_sent_at: null, items: [] } as HardwareRequest;
    wrap(<RequestDetail row={request} canViewAudit={false} view="overview" onView={() => undefined} onClose={() => undefined} />,
      ["accept_request"], "/m/lab/admin/requests?id=31");
    fireEvent.click(await screen.findByRole("button", { name: "Borrower history" }));
    expect(await screen.findByRole("heading", { name: "Activity across the space" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Hide borrower history" })).toHaveAttribute("aria-expanded", "true");
  });
});
