import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { delegableHelperRoles, EventHelperInvites } from "./EventHelperInvites";
import { EventDrawerMore } from "./EventDrawerMore";
import { eventDrawerSurfaces } from "./eventDrawerTabs";
import { eventAccess } from "./eventStaffPermissions";
import type { StaffEvent } from "./eventsApi";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));
vi.mock("./EventStaffAccess", () => ({ EventStaffAccess: () => <div>full staff access</div> }));
vi.mock("./EventOrganizers", () => ({ EventOrganizers: () => <div>organizers</div> }));
vi.mock("./EventCollaborators", () => ({ EventCollaborators: () => <div>collaborators</div> }));

const HELD = ["manage_team", "manage_volunteers", "check_in", "judge"];
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const helperGrant = { id: 7, user: 42, permissions: ["judge"], revoked_at: null };
const ownInvite = { id: 3, permissions: ["check_in"], expires_at: "2999-01-01T00:00:00Z", redeemed_at: null, revoked_at: null };

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("co-organizer helper invitations", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === "POST" && path.endsWith("staff-invites/")) return { id: 9, token: "helper-token" };
      if (init?.method) return helperGrant;
      return page(path.includes("staff-grants") ? [helperGrant] : [ownInvite]);
    });
  });

  it("offers only helper roles and permissions the co-organizer holds, never manage_team", () => {
    expect(delegableHelperRoles(HELD)).toEqual([
      { role: "volunteer", label: "Volunteer", permissions: ["check_in"] },
      { role: "judge", label: "Judge", permissions: ["judge"] },
    ]);
    expect(delegableHelperRoles(["manage_team", "edit_details"])).toEqual([]);
  });

  it("invites a helper with one held role's permissions and shows the link once", async () => {
    wrap(<EventHelperInvites eventId={5} held={HELD} />);
    await screen.findByText(/Invitation #3/);
    const permissions = screen.getByRole("group", { name: "Permissions" });
    expect(within(permissions).getAllByRole("checkbox").map((box) => box.parentElement?.textContent)).toEqual(["Check in attendees"]);
    expect(screen.getByRole("option", { name: "Judge" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Mentor" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Invite email"), { target: { value: "door@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Invite helper" }));
    await screen.findByDisplayValue(/staff\/event-invite#token=helper-token/);
    expect(request).toHaveBeenCalledWith("/admin/events/5/staff-invites/", expect.objectContaining({ method: "POST",
      body: JSON.stringify({ email: "door@example.test", send_email: true, permissions: ["check_in"], role_label: "volunteer" }) }));
  });

  it("revokes the co-organizer's own helper and invitation", async () => {
    wrap(<EventHelperInvites eventId={5} held={HELD} />);
    fireEvent.click(await screen.findByRole("button", { name: "Revoke account #42" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-staff-grants/7/revoke/", expect.objectContaining({ method: "POST" })));
    fireEvent.click(screen.getByRole("button", { name: "Revoke invitation #3" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/event-staff-invites/3/revoke/", expect.objectContaining({ method: "POST" })));
  });

  it("labels a closed invitation by why it closed instead of dropping its action silently", async () => {
    const closed = [
      { ...ownInvite, id: 4, expires_at: "2000-01-01T00:00:00Z" },
      { ...ownInvite, id: 5, redeemed_at: "2026-01-01T00:00:00Z" },
      { ...ownInvite, id: 6, revoked_at: "2026-01-01T00:00:00Z" },
    ];
    request.mockImplementation(async (path: string) => page(path.includes("staff-grants") ? [] : closed));
    wrap(<EventHelperInvites eventId={5} held={HELD} />);
    await screen.findByText(/Invitation #4/);
    expect(screen.getByText("Expired")).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("Revoked")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Revoke invitation/ })).toBeNull();
  });

  it("the drawer's Team section gives a co-organizer helper invitations, not full staff management", async () => {
    const event = { id: 5, status: "published", can_manage_staff: false, staff_permissions: HELD } as unknown as StaffEvent;
    const access = eventAccess(event);
    const surfaces = eventDrawerSurfaces(event, access, ["events.volunteering", "events.hackathons"]);
    expect(surfaces.sections.team).toBe(true);
    wrap(<EventDrawerMore event={event} makerspaceId={1} access={access} surfaces={surfaces} section="team" sectionTabs={[]}
      readOnly={false} onWebsitePublication={() => {}} settings={{} as never} />);
    expect(await screen.findByRole("region", { name: "Helper invitations" })).toBeInTheDocument();
    expect(screen.queryByText("full staff access")).not.toBeInTheDocument();
    expect(screen.queryByText("organizers")).not.toBeInTheDocument();
    expect(screen.queryByText("collaborators")).not.toBeInTheDocument();
  });
});
