// SKIPPED (not run, not type-checked): imported from a development worktree, kept for reference.
// Reason: Not in release 0.12.0: StaffAccountsPanel and lib/api/staffAccounts are not in release 0.12.0.
// Excluded from vitest (vite.config.ts) and outside tsconfig "include"; rewrite against the release code before moving back under src/.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { StaffAccountsPanel } from "./StaffAccountsPanel";
import type { StaffAccount, StaffAccountPolicy } from "../../../../lib/api/staffAccounts";
import { clearAccessToken, setAccessToken } from "../../../../lib/api";
import { setRouteSessionContext } from "../../../../lib/api/sessionContext";
import { expectNoA11yViolations } from "../../../../test/axe";

const policy: StaffAccountPolicy = { creatable_roles: ["inventory_manager", "machine_manager", "handover"], can_manage_space_managers: false,
  email_onboarding_available: true,
  machine_types: [{ id: 3, name: "Laser cutter" }], roles: [] };
const staff = (can: Partial<StaffAccount["can"]> = {}): StaffAccount => ({
  id: 41, username: "operator.forge", display_name: "Operator", email: "operator@example.com", roles: ["inventory_manager"],
  machine_type_ids: [], is_active: true, must_change_password: false, mfa_enabled: true, last_login: null,
  created_at: "2026-10-01T00:00:00Z", invitation_pending: true,
  can: { change_roles: true, set_password: true, deactivate: true, reactivate: false, resend_invite: true, ...can },
});
let rows: StaffAccount[];
let calls: { path: string; method: string; body?: Record<string, unknown> }[];
let currentPolicy: StaffAccountPolicy;
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><StaffAccountsPanel space={7} onAuthRefresh={() => {}} /></MemoryRouter></QueryClientProvider>);
  return client;
}
beforeEach(() => {
  setRouteSessionContext("staff:forge"); setAccessToken("staff-token", "staff:forge");
  rows = [staff()]; calls = []; currentPolicy = policy;
  vi.stubGlobal("fetch", vi.fn(async (url: string, options?: RequestInit) => {
    const path = url.replace(/^.*\/api\/v1/, "");
    const method = options?.method ?? "GET";
    const body = options?.body ? JSON.parse(options.body as string) : undefined;
    calls.push({ path, method, body });
    expect(new Headers(options?.headers).get("Authorization")).toBe("Bearer staff-token");
    let result: unknown;
    if (path.endsWith("/policy")) result = currentPolicy;
    else if (path.includes("machine-types") || path.endsWith("/roles")) throw new Error("Use the authorized staff lifecycle policy.");
    else if (method === "GET") result = { count: rows.length, next: null, previous: null, results: rows };
    else if (path.endsWith("/set-password/")) result = { generated_password: body.generate ? "Once-Only-Secret-98" : null };
    else if (path.endsWith("/deactivate/")) { rows = [{ ...rows[0], is_active: false, can: { ...rows[0].can, deactivate: false, reactivate: true } }]; result = rows[0]; }
    else if (path.endsWith("/reactivate/")) { rows = [{ ...rows[0], is_active: true }]; result = rows[0]; }
    else if (path.endsWith("/resend-invite/")) result = { invitation_sent: true };
    else if (method === "PATCH") { rows = [{ ...rows[0], ...body }]; result = rows[0]; }
    else { result = { account: { ...staff(), display_name: body.display_name, roles: body.roles }, invitation_sent: true }; }
    return new Response(JSON.stringify(result), { status: 200 });
  }));
});
afterEach(() => { clearAccessToken("staff:forge"); setRouteSessionContext("member"); vi.unstubAllGlobals(); });

it("creates a separate staff account with combined roles and machine-type scope", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Create staff account" }));
  const dialog = within(screen.getByRole("dialog"));
  expect(dialog.queryByLabelText("Space Manager")).not.toBeInTheDocument();
  expect(dialog.queryByLabelText("Member")).not.toBeInTheDocument();
  fireEvent.change(dialog.getByLabelText("Name"), { target: { value: "New operator" } });
  fireEvent.change(dialog.getByLabelText("Username"), { target: { value: "new-operator" } });
  fireEvent.click(dialog.getByRole("checkbox", { name: "Machine Manager" }));
  fireEvent.click(dialog.getByRole("checkbox", { name: "Handover" }));
  fireEvent.click(await dialog.findByRole("checkbox", { name: "Laser cutter" }));
  fireEvent.click(dialog.getByRole("button", { name: "Create staff account" }));
  await screen.findByText("Staff account created. Invitation sent.");
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-accounts/", method: "POST", body: {
    display_name: "New operator", username: "new-operator", roles: ["machine_manager", "handover"], machine_type_ids: [3],
  } });
  expect(calls.some(call => /memberships|staff-invitations/.test(call.path))).toBe(false);
  expect(calls.some(call => /machine-types|\/roles$/.test(call.path))).toBe(false);
});

it("shows generated passwords once, copies them, and keeps secrets out of Query caches", async () => {
  const copy = vi.fn(async () => undefined); Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: copy } });
  const client = mount(); fireEvent.click(await screen.findByRole("button", { name: "Set password" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Reset authenticator" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Set password" }));
  expect(await screen.findByLabelText("Generated password")).toHaveValue("Once-Only-Secret-98");
  fireEvent.click(screen.getByRole("button", { name: "Copy password" }));
  await waitFor(() => expect(copy).toHaveBeenCalledWith("Once-Only-Secret-98"));
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-accounts/41/set-password/", method: "POST", body: { generate: true, reset_mfa: true } });
  expect(JSON.stringify(client.getMutationCache().getAll())).not.toContain("Once-Only-Secret-98");
  expect(JSON.stringify(client.getQueryCache().getAll())).not.toContain("Once-Only-Secret-98");
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  fireEvent.click(screen.getByRole("button", { name: "Set password" }));
  expect(screen.queryByLabelText("Generated password")).not.toBeInTheDocument();
  expect(JSON.stringify(localStorage)).not.toContain("Once-Only-Secret-98");
});

it("supports an entered password and clears the input after saving", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Set password" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Generate a password" }));
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: "Manually-set-secret-88" } });
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Set password" }));
  await screen.findByText(/Password set. Previous sessions/);
  expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-accounts/41/set-password/", method: "POST", body: { password: "Manually-set-secret-88", reset_mfa: false } });
});

it("deactivates with a reason, preserves the row, then supports reactivation", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Deactivate" }));
  fireEvent.change(screen.getByLabelText("Reason (optional)"), { target: { value: "Left the team" } });
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Deactivate" }));
  await screen.findByText("Inactive"); expect(screen.getByText("Operator")).toBeInTheDocument();
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-accounts/41/deactivate/", method: "POST", body: { reason: "Left the team" } });
  fireEvent.click(await screen.findByRole("button", { name: "Reactivate" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reactivate" }));
  await screen.findByText("Active");
});

it("hides lifecycle buttons and creation when the server grants no authority", async () => {
  rows = [staff({ change_roles: false, set_password: false, deactivate: false, reactivate: false, resend_invite: false })];
  currentPolicy = { ...policy, creatable_roles: [] }; mount();
  await screen.findByText("Operator");
  for (const name of ["Edit roles", "Set password", "Deactivate", "Reactivate", "Resend invite", "Create staff account"]) expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
});

it("marks pending invitations and resends through the staff-account lifecycle API", async () => {
  mount();
  expect(await screen.findByText("Invitation pending")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Resend invite" }));
  await screen.findByText("Invitation sent.");
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-accounts/41/resend-invite/", method: "POST", body: {} });
  expect(calls.some(call => /memberships|staff-invitations/.test(call.path))).toBe(false);
});

it("keeps the pending marker when resend is forbidden and omits it after acceptance", async () => {
  rows = [staff({ resend_invite: false }), { ...staff({ resend_invite: false }), id: 42, username: "accepted", display_name: "Accepted staff", invitation_pending: false }];
  mount(); await screen.findByText("Operator");
  expect(screen.getAllByText("Invitation pending")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Resend invite" })).not.toBeInTheDocument();
});

it("edits roles through the staff-account route and resends initial invitations", async () => {
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Edit roles" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Handover" }));
  fireEvent.click(screen.getByRole("button", { name: "Save roles" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(calls).toContainEqual({ path: "/admin/makerspaces/7/staff-accounts/41/", method: "PATCH", body: { roles: ["inventory_manager", "handover"], machine_type_ids: [] } });
  fireEvent.click(screen.getByRole("button", { name: "Resend invite" }));
  await screen.findByText("Invitation sent.");
});

it("allows Space Manager creation only when the API policy enables it and keeps that role exclusive", async () => {
  currentPolicy = { ...policy, creatable_roles: ["space_manager", ...policy.creatable_roles], can_manage_space_managers: true };
  mount(); fireEvent.click(await screen.findByRole("button", { name: "Create staff account" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Inventory Manager" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Space Manager" }));
  expect(screen.getByRole("checkbox", { name: "Inventory Manager" })).not.toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Space Manager" })).toBeChecked();
});

it("keeps the staff list and creation form accessible", async () => {
  mount(); await screen.findByText("Operator");
  await expectNoA11yViolations(document.body);
  fireEvent.click(screen.getByRole("button", { name: "Create staff account" }));
  await expectNoA11yViolations(screen.getByRole("dialog"));
});
