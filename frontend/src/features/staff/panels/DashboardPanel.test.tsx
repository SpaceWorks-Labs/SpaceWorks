import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { expectNoA11yViolations } from "../../../test/axe";
import { DashboardPanel } from "./DashboardPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));

vi.mock("../../../lib/api", () => ({ staffRequest }));

const makerspace = {
  id: 7,
  name: "Forge",
  public_code: "forge",
  slug: "forge",
  telegram_group_chat_id: "",
  frontend_domain: null,
  hidden_from_central_directory: false,
};

function renderPanel(canManageMakerspace = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
      <DashboardPanel
        makerspace={makerspace}
        canManageMakerspace={canManageMakerspace}
      />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => { staffRequest.mockReset(); });

describe("DashboardPanel booking issues", () => {
  it.each([
    ["full", ["bookings"], ["bookings"], true],
    ["machine", ["bookings"], ["bookings"], false],
    ["full", [], ["bookings"], false],
    ["full", ["bookings"], [], false],
  ])("uses the other booking tiles' scope, module and tab gates (%s, %j, %j)", async (scope, modules, tabs, visible) => {
    staffRequest.mockResolvedValue({ scope_mode: scope, open_booking_issues: 4 });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <DashboardPanel makerspace={{ ...makerspace, enabled_modules: ["staff_admin", ...modules] }}
        canManageMakerspace={false} allowedTabs={tabs} />
    </MemoryRouter></QueryClientProvider>);
    await revealStats();
    const tile = screen.queryByRole("link", { name: /Booking issues 4/ });
    if (visible) expect(tile).toHaveAttribute("href", "/m/forge/admin/bookings?view=issues");
    else expect(tile).toBeNull();
  });
});

describe("DashboardPanel scope mode", () => {
  it("renders only server-declared machine tiles in restricted mode", async () => {
    staffRequest.mockResolvedValue({
      scope_mode: "machine",
      pending_prints: 1,
      active_prints: 2,
      prints_awaiting_collection: 3,
      warranty_expiring: 4,
      maintenance_overdue: 5,
    });

    renderPanel();

    await revealStats();
    expect(screen.queryByText("Overdue loans")).not.toBeInTheDocument();
    expect(screen.getByText("Maintenance overdue")).toBeVisible();
    expect(screen.getByText("Pending prints")).toBeVisible();
    expect(screen.getByText("Warranties expiring")).toBeVisible();
    expect(screen.queryByText("Pending requests")).not.toBeInTheDocument();
    expect(screen.queryByText("Out of stock")).not.toBeInTheDocument();
  });

  it("keeps the full dashboard tiles in full mode", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", overdue_loans: 2, pending_payments: 0 });

    const { container } = renderPanel(true);

    await revealStats();
    expect(screen.getByText("Overdue loans")).toBeVisible();
    expect(screen.getByText("Pending payments")).toBeVisible();
    expect(screen.getByText("Maintenance overdue")).toBeVisible();
    await expectNoA11yViolations(container);
  });
  it("links only to permitted module-enabled lists with dashboard URL filters", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", low_stock: 2, pending_prints: 3 });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <DashboardPanel makerspace={{ ...makerspace, enabled_modules: ["staff_admin", "machines"] }}
        canManageMakerspace={false} allowedTabs={["inventory", "machines"]} />
    </MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("link", { name: /Out of stock 2/ })).toHaveAttribute("href", "/m/forge/admin/inventory?out_of_stock=true&archived=all");
    expect(screen.queryByRole("link", { name: /Pending prints/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Pending requests/ })).not.toBeInTheDocument();
  });
});

async function revealStats() {
  await waitFor(() => expect(screen.queryByRole("status", { name: "Loading content" })).not.toBeInTheDocument());
  const disclosure = screen.queryByRole("button", { name: "Everything else" });
  if (disclosure) fireEvent.click(disclosure);
}

describe("DashboardPanel lending tiles (decision 224 a)", () => {
  it("keeps overdue loans and problem reports for an Inventory Manager without the accountability tab", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", overdue_loans: 2, open_problem_reports: 1 });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <DashboardPanel makerspace={{ ...makerspace, enabled_modules: ["staff_admin", "reports"] }} canManageMakerspace={false}
        allowedTabs={["requests", "ledger", "needsfix", "inventory"]} />
    </MemoryRouter></QueryClientProvider>);
    await revealStats();
    expect(screen.getByRole("link", { name: /Overdue loans 2/ })).toHaveAttribute("href", "/m/forge/admin/ledger?overdue=true");
    expect(screen.getByRole("link", { name: /Problem reports 1/ })).toHaveAttribute("href", "/m/forge/admin/to-be-fixed?section=problems");
  });

  it("drops the problem-report tile with the reports module", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", overdue_loans: 2, open_problem_reports: 1 });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <DashboardPanel makerspace={{ ...makerspace, enabled_modules: ["staff_admin"] }} canManageMakerspace={false}
        allowedTabs={["requests", "ledger", "needsfix"]} />
    </MemoryRouter></QueryClientProvider>);
    await revealStats();
    expect(screen.getByRole("link", { name: /Overdue loans 2/ })).toBeVisible();
    expect(screen.queryByRole("link", { name: /Problem reports/ })).toBeNull();
  });
});

describe("DashboardPanel tile tone", () => {
  it("keeps the danger signal on overdue loans and attention on queues", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", overdue_loans: 2, pending_requests: 3 });
    renderPanel();
    expect(await screen.findByText("Action needed")).toBeInTheDocument();
    expect(screen.getByText("Needs attention")).toBeInTheDocument();
  });
});

describe("DashboardPanel pending payments (menu-notify carry-over)", () => {
  it("hides the tile when the server omits the count instead of showing a false zero", async () => {
    // An Event Manager has the payments tab but no finance authority: the server leaves the key out.
    staffRequest.mockResolvedValue({ scope_mode: "full", upcoming_events: 1 });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <DashboardPanel makerspace={makerspace} canManageMakerspace={false} allowedTabs={["events", "payments"]} />
    </MemoryRouter></QueryClientProvider>);
    await revealStats();
    expect(screen.queryByText("Pending payments")).not.toBeInTheDocument();
  });

  it("shows the server's count to finance staff", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", pending_payments: 3 });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>
      <DashboardPanel makerspace={makerspace} canManageMakerspace={false} allowedTabs={["payments"]} />
    </MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("link", { name: /Pending payments 3/ })).toHaveAttribute("href", "/m/forge/admin/payments?status=pending");
  });
});

beforeEach(() => setRouteSessionContext("person"));
afterEach(() => setRouteSessionContext("person"));
