import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../../lib/api/errors";
import { StaffBulkInviteDialog, parseEmails } from "./StaffBulkInviteDialog";
import type { StaffRolesPolicy } from "./staffRolesApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async original => ({ ...await original<typeof import("../../../../lib/api")>(), staffRequest }));

const policy: StaffRolesPolicy = { grantable_roles: [{ slug: "event_manager", name: "Event Manager", combinable: true },
  { slug: "booking_manager", name: "Booking Manager", combinable: true }], can_manage_space_managers: false,
  email_invites_available: true, machine_types: [] };
const mount = (onDone = vi.fn()) => render(<QueryClientProvider client={new QueryClient()}>
  <StaffBulkInviteDialog space={7} policy={policy} onClose={vi.fn()} onDone={onDone} /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("decision 248: bulk staff invitations", () => {
  it("splits pasted addresses and drops repeats", () => {
    expect(parseEmails("a@x.org, b@x.org\nA@x.org; c@x.org")).toEqual(["a@x.org", "b@x.org", "c@x.org"]);
  });

  it("sends each row with its own or the default roles", async () => {
    const done = vi.fn();
    staffRequest.mockResolvedValue({ invited: 2, invitation_ids: [1, 2], delivery: ["sent", "sent"] });
    mount(done);
    fireEvent.change(screen.getByLabelText(/Paste email addresses/), { target: { value: "a@x.org\nb@x.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Add to the list" }));
    fireEvent.change(screen.getAllByLabelText("Role")[1], { target: { value: "booking_manager" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Event Manager/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send 2 invitations" }));
    await waitFor(() => expect(done).toHaveBeenCalledWith("2 invitations sent."));
    expect(staffRequest.mock.calls[0][0]).toBe("/admin/makerspaces/7/staff-roles/bulk-invite/");
    expect(JSON.parse(staffRequest.mock.calls[0][1].body).invites).toEqual([
      { email: "a@x.org", roles: ["event_manager"], machine_type_ids: [], machine_ids: [] },
      { email: "b@x.org", roles: ["booking_manager"], machine_type_ids: [], machine_ids: [] },
    ]);
  });

  it("names the failing row on a 409 and invites nobody", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(409, { detail: "no", failed_id: 1, cause: "Already staff here." })));
    mount();
    fireEvent.change(screen.getByLabelText(/Paste email addresses/), { target: { value: "a@x.org b@x.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Add to the list" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Event Manager/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send 2 invitations" }));
    expect(await screen.findByText("Nobody was invited. Row 2 (b@x.org) could not be invited: Already staff here.")).toBeInTheDocument();
  });
});
