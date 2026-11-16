import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { SecuritySettingsPanel } from "./SecuritySettingsPanel";
import type { Makerspace } from "./panels/shared";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api/requests", () => ({ staffRequest }));

const KEY = "security.passkeys_allowed";
const setting = (value: boolean, lock: null | { floor: boolean; note: string; locked_at: string } = null) => ({
  key: KEY, label: "Allow passkeys", description: "Staff may use a passkey.", kind: "bool", default: true,
  choices: [], value, strict_value: false, lock,
});
const payload = (overrides: Record<string, unknown> = {}) => ({
  makerspace_id: 7, settings: [setting(false)], can_edit: true, can_lock: false, edited_as: "space", ...overrides,
});
const pii = { makerspace_id: 7, viewer_is_superadmin: false, pii_visible: true, active: null, space_grants: [], recent: [] };

function respond(security: unknown) {
  staffRequest.mockImplementation((path: string, init?: RequestInit) => {
    if (String(path).endsWith("/pii-access")) return Promise.resolve(pii);
    if (init?.method === "PATCH") return Promise.resolve(payload({ settings: [setting(true)] }));
    return Promise.resolve(security);
  });
}

function renderPanel(path = "/m/lab/admin/security") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><SecuritySettingsPanel makerspace={{ id: 7, name: "Lab" } as Makerspace} /></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("SecuritySettingsPanel", () => {
  it("shows staff MFA as a fixed platform rule, not a switch", async () => {
    respond(payload());
    renderPanel();
    expect(await screen.findByText("Required for every space staff role (platform rule)")).toBeInTheDocument();
    expect(screen.queryByText(/Require MFA for staff/)).not.toBeInTheDocument();
  });

  it("lets the Space Manager change a switch through the security endpoint", async () => {
    respond(payload());
    renderPanel();
    const toggle = await screen.findByRole("checkbox", { name: /Off/ });
    fireEvent.click(toggle);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/security-settings",
      { method: "PATCH", body: JSON.stringify({ values: { [KEY]: true } }) }));
    expect(await screen.findByRole("checkbox", { name: /On/ })).toBeChecked();
    expect(screen.queryByRole("button", { name: /Lock/ })).not.toBeInTheDocument();
  });

  it("shows a platform lock with its note and keeps the forced value", async () => {
    respond(payload({ settings: [setting(false, { floor: false, note: "Insurer requires it", locked_at: "2026-10-26T10:00:00Z" })] }));
    renderPanel();
    expect(await screen.findByText("Locked by platform: Insurer requires it")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Off/ })).toBeDisabled();
  });

  it("offers a lock that forces the stricter value to a superadmin", async () => {
    respond(payload({ can_lock: true, edited_as: "platform", settings: [setting(true)] }));
    renderPanel();
    fireEvent.change(await screen.findByRole("textbox", { name: /Note for the space/ }), { target: { value: "Policy" } });
    fireEvent.click(screen.getByRole("button", { name: "Lock off" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(`/admin/makerspaces/7/security-settings/${encodeURIComponent(KEY)}/lock`,
      { method: "PUT", body: JSON.stringify({ floor: false, note: "Policy" }) }));
  });

  it("is read-only for someone who cannot edit", async () => {
    respond(payload({ can_edit: false }));
    renderPanel();
    expect(await screen.findByRole("checkbox", { name: /Off/ })).toBeDisabled();
  });
  it("opens one routed section at a time, each with its own link (C16)", async () => {
    respond(payload());
    renderPanel("/m/lab/admin/security/key-history");
    expect(await screen.findByRole("heading", { name: "Encryption key history" })).toBeInTheDocument();
    expect(screen.queryByText("Required for every space staff role (platform rule)")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Platform access to personal data" })).toHaveAttribute("href", "/m/lab/admin/security/pii");
    expect(screen.getByRole("link", { name: "Sign-in requirements" })).toHaveAttribute("href", "/m/lab/admin/security/sign-in");
  });
});
