/**
 * Release 0.12.0 module on/off audit: each new cross-module panel renders nothing and fires no
 * request while its owning module or capability is off, and asks again once it is back on.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { memberEventEquipmentEnabled } from "../events/MemberEventEquipment";
import { eventOffersEnabled } from "../shop/eventOffersApi";
import { EventLinkedFinancePanel } from "./EventLinkedFinancePanel";
import { EventWorkshopMachines } from "./EventWorkshopMachines";
import { LoanRepairsPanel } from "./loanRepairs/LoanRepairsPanel";
import { RelatedFactsPanel } from "./RelatedFactsPanel";
import { StaffListContext } from "./StaffListContext";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

function mount(space: Space, child: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "", canShare: false, actorId: 5, actions: [], isSuperadmin: true, makerspace: space }}>
      {child}
    </StaffListContext.Provider>
  </QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockResolvedValue({ request_id: 9, lines: [], results: [], withheld: 0 });
});

describe("module-off gating of 0.12.0 panels", () => {
  it("member event equipment asks only with Events, the request workflow and loans on", () => {
    const on = { modules: ["events", "request_workflow"], features: ["loans.enabled"] };
    expect(memberEventEquipmentEnabled(on)).toBe(true);
    expect(memberEventEquipmentEnabled({ ...on, modules: ["request_workflow"] })).toBe(false);
    expect(memberEventEquipmentEnabled({ ...on, modules: ["events"] })).toBe(false);
    expect(memberEventEquipmentEnabled({ ...on, features: [] })).toBe(false);
    expect(memberEventEquipmentEnabled(null)).toBe(false);
  });

  it("event shop offers need Shop, Events, online shop and event pickup", () => {
    const on = { modules: ["shop", "events"], features: ["shop.online", "shop.event_pickup"] };
    expect(eventOffersEnabled(on)).toBe(true);
    expect(eventOffersEnabled({ ...on, modules: ["shop"] })).toBe(false);
    expect(eventOffersEnabled({ ...on, modules: ["events"] })).toBe(false);
    expect(eventOffersEnabled({ ...on, features: ["shop.online"] })).toBe(false);
  });

  it("loan repairs never asks while inventory.repairs is off, and asks once it is on", async () => {
    const loan = { id: 9, status: "closed_with_issue", makerspace_id: 7 };
    const off = mount({ id: 7, enabled_modules: [], enabled_features: [] }, <LoanRepairsPanel loan={loan} />);
    expect(off.container.innerHTML).toBe("");
    expect(staffRequest).not.toHaveBeenCalled();
    off.unmount();
    // Decision 254: the Inventory switch (`loans.enabled`) masters inventory.repairs, as the server's
    // loan_visibility.LOAN_FEATURES does, so the child alone still answers 404 and is never asked.
    const childOnly = mount({ id: 7, enabled_modules: [], enabled_features: ["inventory.repairs"] }, <LoanRepairsPanel loan={loan} />);
    expect(childOnly.container.innerHTML).toBe("");
    expect(staffRequest).not.toHaveBeenCalled();
    childOnly.unmount();
    mount({ id: 7, enabled_modules: [], enabled_features: ["loans.enabled", "inventory.repairs"] }, <LoanRepairsPanel loan={loan} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(staffRequest.mock.calls[0][0]).toBe("/admin/makerspaces/7/requests/9/repairs");
  });

  it("workshop machines stay hidden without the Machines module", () => {
    const view = mount({ id: 7, enabled_modules: ["events", "bookings"] },
      <EventWorkshopMachines makerspaceId={7} eventId={3} readOnly={false} request={vi.fn() as never} queryKey={["venue"]} />);
    expect(view.container.innerHTML).toBe("");
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("linked finance and related facts stay hidden without their domain module", () => {
    const view = mount({ id: 7, enabled_modules: ["bookings"] }, <>
      <EventLinkedFinancePanel tenant={7} eventId={3} />
      <RelatedFactsPanel tenant={7} kind="event" id={3} />
    </>);
    expect(view.container.innerHTML).toBe("");
    view.unmount();
    const bookingsOff = mount({ id: 7, enabled_modules: ["events"] }, <RelatedFactsPanel tenant={7} kind="booking" id={4} />);
    expect(bookingsOff.container.innerHTML).toBe("");
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("linked finance renders its collapsed section when Events is on, without fetching until opened", () => {
    const view = mount({ id: 7, enabled_modules: ["events"] }, <EventLinkedFinancePanel tenant={7} eventId={3} />);
    expect(view.container.innerHTML).not.toBe("");
    expect(staffRequest).not.toHaveBeenCalled();
  });
});
