import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CommandPalette } from "./CommandPalette";
import { reportCommands } from "./reportCommands";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: request }));

const mount = (allowedTabs: string[], actions: string[] = []) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><CommandPalette makerspaceId={7} makerspaceSlug="forge" allowedTabs={allowedTabs} guestOnly={false} singleTenantLocked={false}
    ownerName="sam" actions={actions} open onOpenChange={vi.fn()} /></MemoryRouter></QueryClientProvider>);

beforeEach(() => { request.mockReset(); request.mockResolvedValue({ results: [] }); });

describe("decision 242 (U6): new search sources in the palette", () => {
  it("names job, shop, payment, incident and guest-pass hits and drops tabs the role cannot open", async () => {
    request.mockResolvedValue({ results: [
      { entity: "jobs", id: 12, label: "Job #12", tab: "machines", query: { job: "12" } },
      { entity: "payments", id: 5, label: "Payment #5", tab: "payments", query: { payment: "5" } },
      { entity: "incidents", id: 3, label: "Burn at laser", tab: "incidents", query: { id: "3" } },
      { entity: "passes", id: 4, label: "Guest pass · ada", tab: "members", query: { section: "guests", pass: "4" } },
    ] });
    mount(["machines", "incidents", "members"]);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "12" } });
    expect(await screen.findByRole("option", { name: "Machine job: Job #12" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Incident: Burn at laser" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Guest pass · ada" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Payment #5/ })).toBeNull();
  });
});

describe("decision 248: new reports are findable by the roles that can open them", () => {
  it("lists only reports the actor's actions admit, behind the Reports tab", () => {
    const keys = (actions: string[]) => reportCommands(actions, ["reports"], false).map(command => command.query.report);
    expect(keys(["manage_machines"])).toEqual(["incidents-register", "machine-jobs"]); // decision 329: retired report not promoted
    expect(keys(["manage_members"])).toEqual(["roster-export", "guest-passes-export", "volunteer-hours-export", "minors-consent-export"]);
    expect(reportCommands(["manage_members"], ["members"], false)).toEqual([]);
    expect(reportCommands([], ["reports"], true)).toHaveLength(10);
  });

  it("shows a report command once the person types", async () => {
    mount(["reports"], ["edit_inventory", "view_inventory"]);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "valuation" } });
    expect(await screen.findByRole("option", { name: "Report: Inventory valuation" })).toBeInTheDocument();
  });
});
