import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setRouteSessionContext } from "../../../../lib/api/sessionContext";
import { DashboardPanel } from "../DashboardPanel";
import { AreaSections } from "./AreaSections";
import { WaitingOnMe } from "./WaitingOnMe";
import { attentionHref, type Attention } from "./attention";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const routing = { slug: "forge", guestOnly: false, singleTenantLocked: false, allowedTabs: ["requests", "ledger", "bookings", "machines"] };
const attention: Attention = {
  areas: [
    { key: "lending", total: 5, items: [
      { key: "pending_requests", count: 3, link: { tab: "requests", filters: { queue: "pending" } } },
      { key: "overdue_loans", count: 2, link: { tab: "ledger", filters: { overdue: "true" } } },
      { key: "due_today_loans", count: 0, link: { tab: "ledger", filters: { due: "today" } } }] },
    { key: "bookings", total: 0, items: [{ key: "pending_bookings", count: 0, link: { tab: "bookings", filters: { status: "pending" } } }] },
  ],
  waiting: [
    { area: "lending", key: "pending_requests", count: 3, link: { tab: "requests", filters: { queue: "pending" } } },
    { area: "lending", key: "overdue_loans", count: 2, link: { tab: "ledger", filters: { overdue: "true" } } },
  ],
  errors: ["machines"],
};
const wrap = (node: React.ReactNode) => render(<MemoryRouter>{node}</MemoryRouter>);

beforeEach(() => { setRouteSessionContext("person"); staffRequest.mockReset(); });

describe("decision 242(j): Waiting on me", () => {
  it("lists what is waiting with deep links, names lending as Inventory, and says which area failed", () => {
    const retry = vi.fn();
    wrap(<WaitingOnMe attention={attention} routing={routing} onRetry={retry} />);
    const link = screen.getByRole("link", { name: /Borrow requests to review.*Inventory.*3/ });
    expect(link).toHaveAttribute("href", "/m/forge/admin/requests?queue=pending");
    expect(screen.getByRole("link", { name: /Overdue loans/ })).toHaveAttribute("href", "/m/forge/admin/ledger?overdue=true");
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load: Machines. These numbers are missing, not zero.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
  });

  it("shows a calm empty state when nothing waits and nothing failed", () => {
    wrap(<WaitingOnMe attention={{ areas: [], waiting: [], errors: [] }} routing={routing} onRetry={vi.fn()} />);
    expect(screen.getByText(/Nothing is waiting on you right now/)).toBeInTheDocument();
  });

  it("does not link a counter to a tab the viewer cannot open", () => {
    expect(attentionHref({ tab: "payments", filters: {} }, routing)).toBeUndefined();
  });

  it("passes the server's real Members section targets through unchanged", () => {
    const href = attentionHref({ tab: "members", filters: { section: "guests" } }, { ...routing, allowedTabs: [...(routing.allowedTabs ?? []), "members"] });
    expect(href).toContain("section=guests");
    expect(href).not.toContain("community");
  });
});

describe("decision 242(j): Waiting on me", () => {
  it("lists what is waiting with deep links, names lending as Inventory, and says which area failed", () => {
    const retry = vi.fn();
    wrap(<WaitingOnMe attention={attention} routing={routing} onRetry={retry} />);
    const link = screen.getByRole("link", { name: /Borrow requests to review.*Inventory.*3/ });
    expect(link).toHaveAttribute("href", "/m/forge/admin/requests?queue=pending");
    expect(screen.getByRole("link", { name: /Overdue loans/ })).toHaveAttribute("href", "/m/forge/admin/ledger?overdue=true");
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load: Machines. These numbers are missing, not zero.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
  });

  it("shows a calm empty state when nothing waits and nothing failed", () => {
    wrap(<WaitingOnMe attention={{ areas: [], waiting: [], errors: [] }} routing={routing} onRetry={vi.fn()} />);
    expect(screen.getByText(/Nothing is waiting on you right now/)).toBeInTheDocument();
  });

  it("does not link a counter to a tab the viewer cannot open", () => {
    expect(attentionHref({ tab: "payments", filters: {} }, routing)).toBeUndefined();
  });
});

describe("decision 242(j): sections by area", () => {
  it("collapses empty areas, shows totals, filters by area and keeps a failed area visible", () => {
    wrap(<AreaSections attention={attention} routing={routing} />);
    const inventory = screen.getByRole("button", { name: /Inventory · Total 5/ });
    expect(inventory).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /Bookings · Total 0/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText(/Couldn't load this area's numbers/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Show area"), { target: { value: "bookings" } });
    expect(screen.queryByRole("button", { name: /Inventory · Total/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Bookings · Total 0/ }));
    expect(screen.getByText("Bookings to approve")).toBeInTheDocument();
  });
});

describe("decision 242(j): the dashboard home", () => {
  const makerspace = { id: 7, name: "Forge", public_code: "forge", slug: "forge", telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false };
  const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><DashboardPanel makerspace={makerspace} canManageMakerspace /></MemoryRouter></QueryClientProvider>);

  it("puts Waiting on me first and moves uncovered tiles to compact numbers", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", pending_requests: 3, overdue_loans: 2, upcoming_events: 4, attention });
    mount();
    expect(await screen.findByRole("heading", { name: "Waiting on me" })).toBeInTheDocument();
    const other = screen.getByRole("region", { name: "Other numbers" });
    expect(within(other).getByText("Upcoming events")).toBeInTheDocument();
    expect(within(other).queryByText("Pending requests")).toBeNull();
  });

  it("keeps the tile row and hides the new counters the server did not send", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", pending_requests: 1 });
    mount();
    expect(await screen.findByText("Pending requests")).toBeInTheDocument();
    expect(screen.queryByText("Due back today")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Waiting on me" })).toBeNull();
  });

  it("shows payments to record when the server sends it", async () => {
    staffRequest.mockResolvedValue({ scope_mode: "full", payments_to_record: 6, due_today_loans: 2 });
    mount();
    expect(await screen.findByText("Payments to record")).toBeInTheDocument();
    expect(screen.getByText("Due back today")).toBeInTheDocument();
  });
});
