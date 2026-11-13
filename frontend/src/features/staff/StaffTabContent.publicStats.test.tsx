import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";

// #205: area consoles gate their public-stats editors on the makerspace's public_site_enabled flag.
// `public_site` is not a module key, so reading it from enabled_modules always hid the editors.
vi.mock("./StaffTabLoaders", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  const probe = (name: string) => (props: { publicSiteEnabled?: boolean }) =>
    <p data-testid={name}>{String(props.publicSiteEnabled)}</p>;
  return { ...actual, MachinesPanel: probe("machines"), EventsPanel: probe("events"), BookingsPanel: probe("bookings") };
});

import { StaffTabContent } from "./StaffTabContent";

const user = { makerspaces: [], superadmin_actions: [] };

function renderTab(activeTab: string, publicSite: boolean) {
  const props = {
    activeTab, isSuperadmin: true, currentUser: user, makerspaces: [], guestOnly: false, printingOnly: false,
    canManageMachines: true, canManageEvents: true, canManageBookings: true, isMachineOnly: false,
    activeMakerspace: { id: 7, name: "Lab", slug: "lab", public_site_enabled: publicSite,
      enabled_modules: ["machines", "events", "bookings"], enabled_features: [] },
  } as unknown as ComponentProps<typeof StaffTabContent>;
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><StaffTabContent {...props} /></MemoryRouter></QueryClientProvider>);
}

describe("area public-stats gate (#205)", () => {
  it.each(["machines", "events", "bookings"])("passes public_site_enabled to the %s console", async (tab) => {
    const { unmount } = renderTab(tab, true);
    expect(await screen.findByTestId(tab)).toHaveTextContent("true");
    unmount();
    renderTab(tab, false);
    expect(await screen.findByTestId(tab)).toHaveTextContent("false");
  });
});
