import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";
import { OrganizationEventAdmission } from "./OrganizationEventAdmission";
import type { PublicEventDetail } from "./eventTicketTypes";

const session = vi.hoisted(() => ({ signedIn: false, hasAccessToken: true, restoreSuccess: true }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual("../../lib/api"),
  getAccessToken: () => session.hasAccessToken ? "test-session" : "",
  refreshAccessToken: async () => {
    session.signedIn = session.restoreSuccess;
    session.hasAccessToken = session.restoreSuccess;
    return session.restoreSuccess;
  },
  memberRequest: async () => {
    if (!session.signedIn) throw new StructuredApiError(401, { detail: "Sign in" });
    return { id: 17 };
  },
  tenantMemberRequest: async () => ({ eligible: true, reason: null, host_waiver: null }),
}));
vi.mock("../members/MemberAuthPanel", () => ({
  MemberAuthPanel: ({ onAuthenticated }: { onAuthenticated: () => void }) =>
    <button onClick={() => { session.signedIn = true; onAuthenticated(); }}>Sign in</button>,
}));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
vi.mock("../../lib/tenant", () => ({ useTenantPath: () => (path: string) => `/m/venue/${path}`,
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } }) }));

const anonymousEvent: PublicEventDetail = {
  title: "Workshop", description: "Workshop details", location: "Host venue",
  starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T12:00:00Z",
  capacity: 10, payment_amount: "0.00", effective_registration_cutoff_at: null,
  image_url: null, status: "published", series: null,
  public_token: "event-one", registration_audience: "participating_organizations",
  registration_open: true, registration_requires_approval: false, availability: "Available",
  custom_form: null, ticket_selection_required: true, ticket_types: [], currency: "USD",
};
const memberTicket = { id: 3, name: "Host members", amount: "0.00", audience: "member", spots_left: 10 } as const;

describe("event ticket projection after authentication", () => {
  beforeEach(() => { session.signedIn = false; session.hasAccessToken = true; session.restoreSuccess = true; });

  it.each([
    ["detail", "sign-in"], ["list", "sign-in"],
    ["detail", "refresh-cookie"], ["list", "refresh-cookie"],
  ] as const)("refreshes both public caches from the %s admission form after %s", async (surface, method) => {
    session.hasAccessToken = method === "sign-in";
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    const detailKey = ["public-event", "venue", "event-one"];
    const listKey = ["public-events", "venue"];
    const unrelatedKey = ["public-event", "other-venue", "event-one"];
    client.setQueryData(unrelatedKey, anonymousEvent);
    const projection = () => ({ ...anonymousEvent, ticket_types: session.signedIn ? [memberTicket] : [] });
    const detail = vi.fn(async () => projection());
    const list = vi.fn(async () => [projection()]);

    function PublicEventQueries() {
      const detailQuery = useQuery({ queryKey: detailKey, queryFn: detail });
      const listQuery = useQuery({ queryKey: listKey, queryFn: list });
      const event = surface === "detail" ? detailQuery.data : listQuery.data?.[0];
      return event ? <OrganizationEventAdmission event={event} makerspaceSlug="venue" /> : null;
    }

    const view = render(<MemoryRouter><QueryClientProvider client={client}>
      <PublicEventQueries />
    </QueryClientProvider></MemoryRouter>);
    const check = await screen.findByRole("button", { name: "Check registration eligibility" });
    await waitFor(() => {
      expect(detail).toHaveBeenCalledOnce();
      expect(list).toHaveBeenCalledOnce();
    });
    expect(client.getQueryData<PublicEventDetail>(detailKey)?.ticket_types).toEqual([]);
    expect(client.getQueryData<PublicEventDetail[]>(listKey)?.[0].ticket_types).toEqual([]);
    fireEvent.click(check);
    if (method === "sign-in") fireEvent.click(await screen.findByRole("button", { name: "Sign in" }));
    fireEvent.click(await screen.findByRole("button", { name: "Register" }));
    const picker = await screen.findByRole("combobox", { name: "Ticket type" });
    expect(screen.getByRole("option", { name: "Host members · Free" })).toBeInTheDocument();
    fireEvent.change(picker, { target: { value: "3" } });
    expect(picker).toHaveValue("3");
    expect(screen.queryByText(/No tickets are available/)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(detail).toHaveBeenCalledTimes(2);
      expect(list).toHaveBeenCalledTimes(2);
    });
    expect(client.getQueryData<PublicEventDetail>(detailKey)?.ticket_types).toEqual([memberTicket]);
    expect(client.getQueryData<PublicEventDetail[]>(listKey)?.[0].ticket_types).toEqual([memberTicket]);
    expect(client.getQueryState(unrelatedKey)?.isInvalidated).toBe(false);
    view.unmount();
    client.clear();
  });

  it("keeps public projections unchanged when session restoration fails", async () => {
    session.hasAccessToken = false;
    session.restoreSuccess = false;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const detailKey = ["public-event", "venue", "event-one"];
    const listKey = ["public-events", "venue"];
    client.setQueryData(detailKey, anonymousEvent);
    client.setQueryData(listKey, [anonymousEvent]);
    const view = render(<QueryClientProvider client={client}>
      <OrganizationEventAdmission event={anonymousEvent} makerspaceSlug="venue" />
    </QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Check registration eligibility" }));
    await screen.findByRole("button", { name: "Sign in" });
    expect(client.getQueryState(detailKey)?.isInvalidated).toBe(false);
    expect(client.getQueryState(listKey)?.isInvalidated).toBe(false);
    expect(screen.queryByRole("button", { name: "Register" })).not.toBeInTheDocument();
    view.unmount(); client.clear();
  });
});
