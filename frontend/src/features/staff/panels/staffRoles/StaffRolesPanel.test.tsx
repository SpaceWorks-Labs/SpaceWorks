import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken } from "../../../../lib/api";
import { setRouteSessionContext } from "../../../../lib/api/sessionContext";
import { expectNoA11yViolations } from "../../../../test/axe";
import { StaffRolesPanel } from "./StaffRolesPanel";
import { staffRolesKey, type StaffRoleRow, type StaffRolesPolicy } from "./staffRolesApi";

const policy: StaffRolesPolicy = {
  grantable_roles: [{ slug: "inventory_manager", name: "Inventory Manager", combinable: true },
    { slug: "machine_manager", name: "Machine Manager", combinable: true }, { slug: "handover", name: "Handover", combinable: true }],
  can_manage_space_managers: false, email_invites_available: true, machine_types: [{ id: 3, name: "Laser cutter" }],
};
const staff = (can: Partial<StaffRoleRow["can"]> = {}): StaffRoleRow => ({
  id: 41, user_id: 900, username: "operator.forge", display_name: "Operator", email: "operator@example.com",
  roles: ["inventory_manager", "handover"], machine_type_ids: [], status: "active", mfa_enabled: true,
  granted_at: "2026-10-01T00:00:00Z", revoked_at: null, revocation_reason: "",
  can: { change_roles: true, revoke: true, restore: false, reset_mfa: false, ...can },
});
let rows: StaffRoleRow[];
let calls: { path: string; method: string; body?: Record<string, unknown> }[];
let currentPolicy: StaffRolesPolicy;
let refusal: { path: RegExp; status: number; body: Record<string, unknown> } | undefined;
let invitesOff: boolean;

function mount(canManageRoles = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter>
    <StaffRolesPanel space={7} onAuthRefresh={() => {}} canManageRoles={canManageRoles} />
  </MemoryRouter></QueryClientProvider>);
  return client;
}
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

beforeEach(() => {
  setRouteSessionContext("person"); setAccessToken("staff-token", "person");
  rows = [staff()]; calls = []; currentPolicy = policy; refusal = undefined; invitesOff = false;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    const path = url.replace(/^.*\/api\/v1/, "");
    const method = options?.method ?? "GET";
    const body = options?.body ? JSON.parse(options.body as string) : undefined;
    calls.push({ path, method, body });
    if (refusal && refusal.path.test(path) && method !== "GET") return json(refusal.body, refusal.status);
    if (path.startsWith("/admin/memberships")) return json({ results: [{ id: 5, user: { id: 77, username: "maya", display_name: "Maya Rao" } }] });
    if (path.includes("/staff-invitations") && invitesOff) return json({ detail: "Invitations are off.", code: "feature_disabled",
      feature: "staff.invitations" }, 404);
    if (path.includes("/staff-invitations")) return json({ count: 1, next: null, previous: null, results: [{ id: 8, email: "new@example.test",
      role_name: "Handover", roles: ["handover"], machine_type_ids: [], expires_at: "2099-01-01T00:00:00Z", accepted_at: null, revoked_at: null,
      created_at: "2026-10-01T00:00:00Z" }] });
    if (method === "GET") return json({ count: rows.length, next: null, previous: null, results: rows, policy: currentPolicy });
    if (path.endsWith("/revoke/")) { rows = [{ ...rows[0], status: "revoked", can: { ...rows[0].can, revoke: false, restore: true } }]; return json(rows[0]); }
    if (body?.email) return json({ kind: "invited", staff_role: null, invitation_id: 12, delivery_status: body.email === "queued@example.test" ? "pending" : "sent" }, 201);
    return json({ kind: "granted", staff_role: { ...staff(), id: 50, user_id: body?.user_id }, invitation_id: null, delivery_status: null }, 201);
  }));
});
afterEach(() => { clearAccessToken("person"); setRouteSessionContext("person"); vi.unstubAllGlobals(); });

it("lists staff rows with role names, two-step status and policy-driven actions", async () => {
  mount();
  expect(await screen.findByText("Operator")).toBeInTheDocument();
  expect(screen.getByText("operator.forge · operator@example.com")).toBeInTheDocument();
  expect(screen.getByText("Inventory Manager + Handover")).toBeInTheDocument();
  expect(screen.getByText("Two-step sign-in on")).toBeInTheDocument();
  expect(screen.getByText("Active")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add staff" })).toBeInTheDocument();
  expect(calls[0]).toEqual({ path: "/admin/makerspaces/7/staff-roles/?page=1&include_revoked=0", method: "GET", body: undefined });
  fireEvent.click(screen.getByRole("checkbox", { name: "Show revoked" }));
  await waitFor(() => expect(calls.some(call => call.path.endsWith("include_revoked=1"))).toBe(true));
  await expectNoA11yViolations(document.body);
});

it("grants roles to a community member of this space by user id", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Add staff" }));
  const dialog = within(screen.getByRole("dialog"));
  fireEvent.change(dialog.getByLabelText("Find a member"), { target: { value: "maya" } });
  fireEvent.click(await dialog.findByRole("radio", { name: /Maya Rao/ }));
  fireEvent.click(dialog.getByRole("checkbox", { name: "Machine Manager" }));
  fireEvent.click(await dialog.findByRole("checkbox", { name: "Laser cutter" }));
  fireEvent.click(dialog.getByRole("button", { name: "Grant roles" }));
  await screen.findByText("Staff roles granted to Maya Rao.");
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-roles/", method: "POST", body: { user_id: 77, roles: ["machine_manager"], machine_type_ids: [3], machine_ids: [] } });
  expect(calls.some(call => call.path === "/admin/memberships?makerspace_id=7&status=active&q=maya")).toBe(true);
});

it("invites by email and reports delivery without any link", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Add staff" }));
  const dialog = within(screen.getByRole("dialog"));
  fireEvent.click(dialog.getByRole("radio", { name: "Invite by email" }));
  fireEvent.change(dialog.getByLabelText("Email"), { target: { value: "new@example.test" } });
  fireEvent.click(dialog.getByRole("checkbox", { name: "Handover" }));
  fireEvent.click(dialog.getByRole("button", { name: "Send invitation" }));
  await screen.findByText("Invitation email sent.");
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-roles/", method: "POST", body: { email: "new@example.test", roles: ["handover"], machine_type_ids: [], machine_ids: [] } });
  expect(screen.queryByLabelText(/link/i)).not.toBeInTheDocument();
});

it("shows a queued state while the worker is still sending the invitation email", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Add staff" }));
  const dialog = within(screen.getByRole("dialog"));
  fireEvent.click(dialog.getByRole("radio", { name: "Invite by email" }));
  fireEvent.change(dialog.getByLabelText("Email"), { target: { value: "queued@example.test" } });
  fireEvent.click(dialog.getByRole("checkbox", { name: "Handover" }));
  fireEvent.click(dialog.getByRole("button", { name: "Send invitation" }));
  await screen.findByText("Invitation email queued. It is being sent now.");
});

it("hides email invitations when the policy has them off", async () => {
  currentPolicy = { ...policy, email_invites_available: false };
  mount(true);
  fireEvent.click(await screen.findByRole("button", { name: "Add staff" }));
  const dialog = within(screen.getByRole("dialog"));
  expect(dialog.queryByRole("radio", { name: "Invite by email" })).not.toBeInTheDocument();
  expect(dialog.getByLabelText("Find a member")).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Invitations", hidden: true })).not.toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Role definitions", hidden: true })).toBeInTheDocument();
  expect(calls.some(call => call.path.includes("/staff-invitations"))).toBe(false);
});

it("falls back to Staff when refreshed policy disables the selected Invitations tab", async () => {
  const client = mount(true);
  fireEvent.click(await screen.findByRole("tab", { name: "Invitations" }));
  expect(await screen.findByText("new@example.test")).toBeInTheDocument();
  currentPolicy = { ...policy, email_invites_available: false };
  await act(async () => { await client.invalidateQueries({ queryKey: staffRolesKey(7) }); });
  await waitFor(() => expect(screen.getByRole("tab", { name: "Staff" })).toHaveAttribute("aria-selected", "true"));
  expect(screen.queryByRole("tab", { name: "Invitations" })).not.toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Role definitions" })).toBeInTheDocument();
  expect(screen.getByText("Operator")).toBeInTheDocument();
});

it("revokes through the revoke route with the optional reason", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
  const dialog = within(screen.getByRole("dialog"));
  fireEvent.change(dialog.getByLabelText("Reason (optional)"), { target: { value: "Left the team" } });
  fireEvent.click(dialog.getByRole("button", { name: "Revoke" }));
  await screen.findByText("Revoked");
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-roles/41/revoke/", method: "POST", body: { reason: "Left the team" } });
});

it("shows the mapped copy for a last_manager refusal", async () => {
  refusal = { path: /\/revoke\/$/, status: 409, body: { detail: "raw server text", code: "last_manager" } };
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Revoke" }));
  expect(await screen.findByText("A makerspace keeps at least one active Space Manager.")).toBeInTheDocument();
  expect(screen.queryByText("raw server text")).not.toBeInTheDocument();
});

it("offers Reset authenticator only when the row allows it, and requires a reason", async () => {
  rows = [staff(), { ...staff({ reset_mfa: true }), id: 42, user_id: 901, display_name: "Second" }];
  mount(); await screen.findByText("Second");
  const buttons = screen.getAllByRole("button", { name: "Reset authenticator" });
  expect(buttons).toHaveLength(1);
  fireEvent.click(buttons[0]);
  const dialog = within(screen.getByRole("dialog"));
  const confirm = dialog.getByRole("button", { name: "Reset authenticator" });
  expect(confirm).toBeDisabled();
  fireEvent.change(dialog.getByLabelText("Reason"), { target: { value: "Lost phone" } });
  fireEvent.click(confirm);
  await screen.findByText(/authenticator was reset/);
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-roles/42/mfa-reset", method: "POST", body: { reason: "Lost phone" } });
});

it("lists invitations without links and resends with delivery copy", async () => {
  mount(); fireEvent.click(await screen.findByRole("tab", { name: "Invitations" }));
  expect(await screen.findByText("new@example.test")).toBeInTheDocument();
  expect(screen.queryByText(/accept|link/i)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Resend" }));
  await screen.findByText("The email could not be sent; ask them to check the address and resend.");
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-invitations/8/resend", method: "POST", body: {} });
});

it("treats the invitations feature being off as an info state, not a crash", async () => {
  invitesOff = true;
  mount(); fireEvent.click(await screen.findByRole("tab", { name: "Invitations" }));
  expect(await screen.findByText("Staff invitations are turned off for this makerspace.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("never shows password controls", async () => {
  rows = [staff({ restore: true, reset_mfa: true })];
  mount(true); await screen.findByText("Operator");
  fireEvent.click(screen.getByRole("button", { name: "Add staff" }));
  expect(document.body.textContent?.toLowerCase()).not.toContain("password");
});
