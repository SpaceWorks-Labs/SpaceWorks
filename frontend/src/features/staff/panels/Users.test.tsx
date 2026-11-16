import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken, type StaffAuthUser } from "../../../lib/api";
import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { expectNoA11yViolations } from "../../../test/axe";
import { Users } from "./Users";
import type { Makerspace } from "./shared";
import type { StaffRole } from "./rolesApi";
import type { StaffRoleRow, StaffRolesPolicy } from "./staffRoles/staffRolesApi";

const space = (id: number): Makerspace => ({ id, name: `Space ${id}`, slug: `space-${id}`, public_code: `LAB${id}`,
  telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false });
const spaces = [space(7), space(8)];
const actor = { makerspaces: [{ id: 7, actions: ["manage_makerspace"] }, { id: 8, actions: [] }] } as StaffAuthUser;
const policy: StaffRolesPolicy = { grantable_roles: [{ slug: "space_manager", name: "Space Manager", combinable: false },
  { slug: "inventory_manager", name: "Inventory Manager", combinable: true }], can_manage_space_managers: true,
  email_invites_available: true, machine_types: [{ id: 3, name: "Laser cutter" }] };
const row = (id: number): StaffRoleRow => ({ id: 41, user_id: 900 + id, username: `staff-${id}`, display_name: `Staff ${id}`, email: "",
  roles: ["space_manager"], machine_type_ids: [], status: "active", mfa_enabled: false, granted_at: "2026-10-01T00:00:00Z",
  revoked_at: null, revocation_reason: "", can: { change_roles: true, revoke: true, restore: false, reset_mfa: false } });
const role = (id: number): StaffRole => ({ id: 1, makerspace_id: id, name: `Space ${id} Manager`, slug: "space_manager", granted_actions: [],
  exclusive: true, combinable: false, member_count: 1, legacy_role: "space_manager", is_default: true, is_protected: true,
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z" });
let calls: { path: string; method: string; body?: Record<string, unknown> }[];
let failingSpace: number | undefined;

function mount(makerspaces = spaces, isSuperadmin = false, currentUser = actor) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = (rows: Makerspace[], user = currentUser) => <QueryClientProvider client={client}><MemoryRouter>
    <Users makerspaces={rows} isSuperadmin={isSuperadmin} currentUser={user} onAuthRefresh={() => {}} />
  </MemoryRouter></QueryClientProvider>;
  const result = render(view(makerspaces));
  return { ...result, rerenderUsers: (rows: Makerspace[], user = currentUser) => result.rerender(view(rows, user)) };
}

beforeEach(() => {
  setRouteSessionContext("platform"); setAccessToken("platform-token", "platform");
  calls = []; failingSpace = undefined;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    const path = url.replace(/^.*\/api\/v1/, "");
    const method = options?.method ?? "GET";
    const body = options?.body ? JSON.parse(options.body as string) : undefined;
    calls.push({ path, method, body });
    const id = Number(path.match(/makerspaces\/(\d+)/)?.[1]);
    if (id === failingSpace && path.includes("staff-roles")) return new Response(JSON.stringify({ detail: "Space unavailable" }), { status: 403 });
    let result: unknown;
    if (path === "/admin/makerspaces" && method === "POST") result = space(9);
    else if (path.endsWith("/roles")) result = [role(id)];
    else if (method === "POST" && path.endsWith("/staff-roles/")) result = { kind: "invited", staff_role: null, invitation_id: 3, delivery_status: "sent" };
    else {
      const rows = path.includes("staff-roles") && id !== 9 ? [row(id)] : [];
      result = { count: rows.length, next: null, previous: null, results: rows, policy };
    }
    return new Response(JSON.stringify(result), { status: 200 });
  }));
});
afterEach(() => { clearAccessToken("platform"); setRouteSessionContext("person"); vi.unstubAllGlobals(); });

it("shows the read-only Roles tab only with role authority and falls back to Staff", async () => {
  mount(); await screen.findByText("Staff 7");
  fireEvent.click(screen.getByRole("tab", { name: "Role definitions" }));
  await screen.findByText("Space 7 Manager");
  await expectNoA11yViolations(document.body);
  fireEvent.change(screen.getByLabelText("Makerspace"), { target: { value: "8" } });
  await screen.findByText("Staff 8");
  expect(screen.queryByRole("tab", { name: "Role definitions" })).not.toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Staff" })).toHaveAttribute("aria-selected", "true");
  expect(calls.some(call => call.path === "/admin/makerspaces/8/roles")).toBe(false);
});

it("falls back to Staff when refreshed permissions remove the active Roles tab", async () => {
  const view = mount();
  fireEvent.click(await screen.findByRole("tab", { name: "Role definitions" }));
  await screen.findByText("Space 7 Manager");
  view.rerenderUsers(spaces, { makerspaces: [] } as unknown as StaffAuthUser);
  await screen.findByText("Staff 7");
  expect(screen.queryByRole("tab", { name: "Role definitions" })).not.toBeInTheDocument();
});

it("scopes staff actions to the selected makerspace", async () => {
  mount(spaces, true, { makerspaces: [] } as unknown as StaffAuthUser);
  await screen.findByText("Staff 7");
  fireEvent.change(screen.getByLabelText("Makerspace"), { target: { value: "8" } });
  await screen.findByText("Staff 8");
  fireEvent.click(screen.getByRole("button", { name: "Add staff" }));
  const dialog = within(screen.getByRole("dialog"));
  fireEvent.click(dialog.getByRole("radio", { name: "Invite by email" }));
  fireEvent.change(dialog.getByLabelText("Email"), { target: { value: "first@example.test" } });
  fireEvent.click(dialog.getByRole("checkbox", { name: "Space Manager" }));
  fireEvent.click(dialog.getByRole("button", { name: "Send invitation" }));
  await screen.findByText("Invitation email sent.");
  expect(calls).toContainEqual({ path: "/admin/makerspaces/8/staff-roles/", method: "POST", body: {
    email: "first@example.test", roles: ["space_manager"], machine_type_ids: [], machine_ids: [] } });
});

it("keeps the makerspace switcher available after a list error", async () => {
  failingSpace = 7; mount(spaces, true);
  await waitFor(() => expect(screen.getByText("Space unavailable")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Makerspace"), { target: { value: "8" } });
  await screen.findByText("Staff 8");
});

it("selects a valid makerspace when spaces arrive asynchronously or the selection disappears", async () => {
  const view = mount([]);
  await screen.findByText("No makerspaces available for this account.");
  view.rerenderUsers(spaces); await screen.findByText("Staff 7");
  fireEvent.change(screen.getByLabelText("Makerspace"), { target: { value: "8" } });
  await screen.findByText("Staff 8");
  view.rerenderUsers([spaces[0]]); await screen.findByText("Staff 7");
});

it("selects a newly created makerspace without opening any account form", async () => {
  mount(spaces, true);
  fireEvent.click(screen.getByRole("button", { name: "Create makerspace" }));
  const wizard = within(screen.getByRole("dialog"));
  fireEvent.change(wizard.getByLabelText("Name"), { target: { value: "Space 9" } });
  fireEvent.change(wizard.getByLabelText("Public code"), { target: { value: "LAB9" } });
  fireEvent.change(wizard.getByLabelText("Slug"), { target: { value: "space-9" } });
  fireEvent.click(wizard.getByLabelText("New organization"));
  for (let step = 0; step < 4; step++) fireEvent.click(wizard.getByRole("button", { name: "Next" }));
  fireEvent.click(wizard.getByRole("button", { name: "Create makerspace" }));
  await waitFor(() => expect(screen.getByLabelText("Makerspace")).toHaveValue("9"));
  await screen.findByText(/No active staff here/);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  const creation = calls.find(call => call.path === "/admin/makerspaces" && call.method === "POST");
  expect(creation?.body?.creation_setup).not.toHaveProperty("first_staff_invite");
});
