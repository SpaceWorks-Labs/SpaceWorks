import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../areaOverview/allowedTabsContext";
import { useCrossLink } from "../crossLinks/staffHref";
import { ConsoleMemberActivity } from "./ConsoleMemberActivity";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

function wrap(node: ReactNode, tabs: string[], path: string) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AllowedTabsContext.Provider value={tabs}>{node}</AllowedTabsContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}

function PersonLink() {
  const link = useCrossLink();
  return <span data-testid="href">{link("members", { member: 21 }) ?? "none"}</span>;
}

describe("member 360 without the Members tab (C30)", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockResolvedValue({ member_id: 21, areas: [], errors: [] }); });

  it("keeps a person link on the current tab, opening the member drawer there", () => {
    wrap(<PersonLink />, ["bookings"], "/m/lab/admin/bookings?view=issues");
    expect(screen.getByTestId("href")).toHaveTextContent("/m/lab/admin/bookings?view=issues&member=21");
  });

  it("still links into Members when that tab is allowed", () => {
    wrap(<PersonLink />, ["members"], "/m/lab/admin/bookings");
    expect(screen.getByTestId("href")).toHaveTextContent("/m/lab/admin/members?member=21");
  });

  it("opens the drawer for an area manager on their own tab", async () => {
    wrap(<ConsoleMemberActivity makerspaceId={4} activeTab="bookings" actions={["manage_bookings"]} isSuperadmin={false} />, ["bookings"], "/m/lab/admin/bookings?member=21");
    expect(await screen.findByRole("heading", { name: "Activity across the space" })).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/members/21/activity", expect.anything());
  });

  it("is not mounted for a handover-only desk or on tabs with their own drawer", () => {
    wrap(<><ConsoleMemberActivity makerspaceId={4} activeTab="requests" actions={["issue_request"]} isSuperadmin={false} />
      <ConsoleMemberActivity makerspaceId={4} activeTab="members" actions={["manage_members"]} isSuperadmin={false} /></>, ["requests"], "/m/lab/admin/requests?member=21");
    expect(api.staffRequest).not.toHaveBeenCalled();
  });
});
