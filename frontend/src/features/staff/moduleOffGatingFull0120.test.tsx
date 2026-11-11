/**
 * Full per-module on/off audit, release 0.12.0 (decisions 218, 223, 225): every capability added
 * in 221-224 has no nav, tab, section or request while it (or its parent module) is off.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { capabilityOn, FEATURE_DEFINITIONS } from "../../lib/features";
import { MemberCommunityArea } from "../community/member/MemberCommunityArea";
import { communityMemberTabs } from "../community/staff/CommunityMemberTabs";
import { MemberHistoryLinks } from "../members/MemberHistoryLinks";
import { StaffCheckInDialog } from "../presence/StaffCheckInDialog";
import { InventoryLendingFlags } from "./panels/InventoryLendingFlags";
import { emptyForm, type ItemForm } from "./panels/InventoryPanelShared";
import { StaffListContext } from "./StaffListContext";
import { filterTabsByEnabledModules } from "./staffTabs";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<typeof import("../../lib/api")>("../../lib/api")), staffRequest }));
vi.mock("../guestPasses/member/MyGuestPasses", () => ({ MyGuestPasses: () => <p>section: my passes</p> }));
vi.mock("../guestPasses/member/DayPassShop", () => ({ DayPassShop: () => <p>section: day passes</p> }));
vi.mock("../guestPasses/member/BringAGuest", () => ({ BringAGuest: () => <p>section: bring a guest</p> }));
vi.mock("../community/member/GuardianConsentPanel", () => ({ GuardianConsentPanel: () => <p>section: guardian consent</p> }));
vi.mock("../community/member/VolunteerLog", () => ({ VolunteerLog: () => <p>section: volunteer log</p> }));
vi.mock("../community/member/OwnConsentStatusCard", () => ({ OwnConsentStatusCard: () => <p>section: own consent status</p> }));

// Backend parents (capability_definitions_r2_guest_passes / _l3a / _l3b); the backend guard pins labels.
const NEW_KEYS: [string, string | null][] = [
  ["membership.guest_passes", "membership"], ["membership.day_passes", "membership"],
  ["events.guest_passes", "events"], ["membership.minors", "membership"],
  ["membership.volunteer_credit", "membership"], ["membership.join_funnel", "membership"],
  ["membership.wallet_passes", "membership"], ["bookings.organization_bookings", "bookings"],
  ["machines.induction_events", "machines"], ["machines.supervised_sessions", "machines"],
  ["safety.incidents", null],
];

describe("features.ts mirrors the new capabilities", () => {
  it.each(NEW_KEYS)("%s has parent %s and is off while that parent is off", (key, parent) => {
    expect(FEATURE_DEFINITIONS.find(feature => feature.key === key)?.parent_module).toBe(parent);
    expect(capabilityOn({ enabled_modules: parent ? [parent] : [], enabled_features: [key] }, key)).toBe(true);
    expect(capabilityOn({ enabled_modules: parent ? [parent] : [], enabled_features: [] }, key)).toBe(false);
    if (parent) expect(capabilityOn({ enabled_modules: [], enabled_features: [key] }, key)).toBe(false);
  });
});

describe("staff navigation", () => {
  it("shows the incident register only with safety.incidents and Analytics only with its module", () => {
    expect(filterTabsByEnabledModules(["incidents", "analytics"], { enabled_modules: ["staff_admin"], enabled_features: [] })).toEqual([]);
    expect(filterTabsByEnabledModules(["incidents", "analytics"],
      { enabled_modules: ["staff_admin", "analytics"], enabled_features: ["safety.incidents"] })).toEqual(["incidents", "analytics"]);
  });

  it("adds each community tab only with its capability and none with membership off", () => {
    const all = ["membership.guest_passes", "membership.minors", "membership.volunteer_credit"];
    expect(communityMemberTabs(all, false)).toEqual([]);
    expect(communityMemberTabs([], true)).toEqual([]);
    expect(communityMemberTabs(all, true).map(tab => tab.key)).toEqual(["guests", "minors", "volunteering"]);
    expect(communityMemberTabs(["membership.minors"], true).map(tab => tab.key)).toEqual(["minors"]);
  });
});

describe("member sections", () => {
  const area = (features: string[], activeMember: boolean) =>
    render(<MemberCommunityArea makerspaceId={3} memberBase="/m/x/member" features={features} activeMember={activeMember} />);

  it("renders nothing with every switch off", () => {
    const { container } = area([], true);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows each section only with its own switch", () => {
    area(["membership.guest_passes", "membership.minors", "membership.volunteer_credit"], true);
    for (const name of ["my passes", "bring a guest", "guardian consent", "own consent status", "volunteer log"]) {
      expect(screen.getByText(`section: ${name}`)).toBeInTheDocument();
    }
    expect(screen.queryByText("section: day passes")).toBeNull();
  });

  it("needs guest passes as well as day passes for the day-pass shop", () => {
    const { unmount } = area(["membership.day_passes"], false);
    expect(screen.queryByText("section: day passes")).toBeNull();
    unmount();
    area(["membership.guest_passes", "membership.day_passes"], false);
    expect(screen.getByText("section: day passes")).toBeInTheDocument();
  });

  it("lists supervised sessions only with the machines module and the switch", () => {
    const { unmount } = render(<MemberHistoryLinks slug="x" modules={["machines"]} features={[]} />);
    expect(screen.queryByText("Supervised sessions")).toBeNull();
    unmount();
    const second = render(<MemberHistoryLinks slug="x" modules={[]} features={["machines.supervised_sessions"]} />);
    expect(screen.queryByText("Supervised sessions")).toBeNull();
    second.unmount();
    render(<MemberHistoryLinks slug="x" modules={["machines"]} features={["machines.supervised_sessions"]} />);
    expect(screen.getByText("Supervised sessions")).toBeInTheDocument();
  });
});

describe("staff check-in with guest passes off", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequest.mockImplementation(async (path: string) => path.includes("check-in-guests") ? { results: [] } : { results: [] });
  });

  const dialog = (features: string[]) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, makerspace: { id: 3, enabled_modules: ["membership"], enabled_features: features } }}>
      <StaffCheckInDialog makerspaceId={3} presets={[60]} onClose={() => undefined} onDone={() => undefined} />
    </StaffListContext.Provider>
  </QueryClientProvider>);

  it("never asks for guest-pass holders while the switch is off", async () => {
    dialog([]);
    fireEvent.change(screen.getByLabelText(/Find a member or guest/), { target: { value: "grace" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(expect.stringContaining("/admin/memberships")));
    expect(staffRequest.mock.calls.some(([path]) => String(path).includes("check-in-guests"))).toBe(false);
  });

  it("asks again once it is on", async () => {
    dialog(["membership.guest_passes"]);
    fireEvent.change(screen.getByLabelText(/Find a member or guest/), { target: { value: "grace" } });
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("check-in-guests"))).toBe(true));
  });
});

describe("event-only flag with Events off", () => {
  function Harness({ start, children }: { start: ItemForm; children?: ReactNode }) {
    const [form, setForm] = useState(start);
    return <>{children}<InventoryLendingFlags form={form} setForm={updater => setForm(current => updater(current))}
      makerspace={{ enabled_modules: [], enabled_features: [] }} /></>;
  }

  it("hides the box for a new item but keeps it on an already flagged one so staff can clear it", () => {
    const { unmount } = render(<Harness start={emptyForm} />);
    expect(screen.queryByText(/Lend only at events/)).toBeNull();
    unmount();
    render(<Harness start={{ ...emptyForm, event_only: true }} />);
    const box = screen.getByRole("checkbox", { name: /Lend only at events/ });
    expect(box).toBeChecked();
    fireEvent.click(box);
    expect(box).not.toBeChecked();
  });
});
