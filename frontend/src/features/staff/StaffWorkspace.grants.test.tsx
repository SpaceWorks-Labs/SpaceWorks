import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StaffAuthUser } from "../../lib/api";
import { StaffApp } from "./StaffApp";

const { session, accessible } = vi.hoisted(() => ({ session: vi.fn(), accessible: vi.fn() }));
vi.mock("./useConsoleSession", () => ({ useConsoleSession: session }));
vi.mock("./eventStaffGrantsApi", () => ({ useAccessibleEvents: accessible }));
// The shell's navigation is built from allowedTabs; print them instead of rendering the sidebar.
vi.mock("./StaffShell", () => ({ StaffShell: ({ allowedTabs, children }: { allowedTabs: string[]; children: React.ReactNode }) => <><p>Tabs: {allowedTabs.join(", ")}</p>{children}</> }));
vi.mock("./StaffTabLoaders", async () => ({
  ...await vi.importActual<typeof import("./StaffTabLoaders")>("./StaffTabLoaders"),
  OrganizationsPanel: () => <h2>Organization governance</h2>,
}));
vi.mock("./EventDrawer", () => ({ EventDrawer: () => null }));
vi.mock("./EventSeriesDrawer", () => ({ EventSeriesDrawer: () => null }));

const grants: NonNullable<StaffAuthUser["event_grants"]> = [
  { event_id: null, series_id: 70, makerspace_id: 7, makerspace_slug: "other", title: "Other tenant series", source: "event_grant", permissions: ["check_in"] },
  { event_id: 81, series_id: null, makerspace_id: 8, makerspace_slug: "locked", title: "Locked tenant event", source: "event_grant", permissions: ["check_in"] },
  { event_id: null, series_id: 80, makerspace_id: 8, makerspace_slug: "locked", title: "Locked tenant series", source: "event_grant", permissions: ["check_in"] },
];
function setup(path: string) {
  // The shell reads the unread-notification count, so the console needs a query client.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><StaffApp /></MemoryRouter></QueryClientProvider>);
}

describe("mixed and single-tenant event grant navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    accessible.mockReturnValue({ data: { results: [] } });
    session.mockReturnValue({
      restoring: false,
      user: { username: "governor", role: "staff", is_superuser: false, makerspaces: [], event_grants: grants },
      recovery: { data: null }, makerspaces: { data: [], isLoading: false }, consoleMakerspaces: [], platform: false,
      singleTenantLocked: false, selected: null, tenant: { makerspaceId: null },
    });
  });

  it("keeps direct organization governance navigation for an actor with no makerspace actions and event grants", async () => {
    setup("/admin/organizations");
    expect(await screen.findByRole("heading", { name: "Organization governance" })).toBeInTheDocument();
    expect(screen.getByText("Tabs: granted, organizations, organized, organization-analytics")).toBeInTheDocument();
    expect(screen.queryByText("Access denied")).not.toBeInTheDocument();
    expect(accessible).not.toHaveBeenCalled();
  });

  it.each([{ eventGrants: grants }, { eventGrants: [...grants].reverse() }])("uses the bootstrap tenant ID for events and series regardless of grant ordering", async ({ eventGrants }) => {
    session.mockReturnValue({ ...session(),
      user: { ...session().user, event_grants: eventGrants },
      singleTenantLocked: true, selected: 8, tenant: { makerspaceId: 8 },
      // Grant-only users have no makerspace list row to supply the tenant ID.
      activeMakerspace: undefined,
    });
    setup("/admin/assigned-events");
    // The assigned-resources lists are lazy chunks; allow for their first load under a busy suite.
    await screen.findByRole("button", { name: /Locked tenant series/ }, { timeout: 5000 });
    expect(accessible).toHaveBeenCalledWith(1, 8);
    expect(screen.queryByRole("button", { name: /Other tenant series/ })).not.toBeInTheDocument();
    expect(screen.getByText("Tabs: granted")).toBeInTheDocument();
  });

  it("retains cross-tenant assigned events in the central console", async () => {
    setup("/admin/assigned-events");
    await waitFor(() => expect(accessible).toHaveBeenCalledWith(1, undefined));
    expect(screen.getByRole("button", { name: /Other tenant series/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Locked tenant series/ })).toBeInTheDocument();
  });
});
