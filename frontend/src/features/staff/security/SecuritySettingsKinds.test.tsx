import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { expectNoA11yViolations } from "../../../test/axe";
import { SecuritySettingsPanel } from "../SecuritySettingsPanel";
import type { Makerspace } from "../panels/shared";
import { parseCidr, within as cidrWithin } from "./cidr";
import { strictnessProblem } from "./securityRules";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api/requests", () => ({ staffRequest }));

type Lock = { floor: unknown; note: string; locked_at: string } | null;
const lock = (floor: unknown, note = ""): Lock => ({ floor, note, locked_at: "2026-11-01T10:00:00Z" });
const row = (key: string, kind: string, value: unknown, extra: Record<string, unknown> = {}) => ({
  key, kind, value, label: key, description: `${key} help`, default: value, choices: [], strict_value: null, lock: null, ...extra,
});
const SESSION = "security.staff_session_max_hours";
const IDLE = "security.staff_idle_timeout_minutes";
const CAPTCHA = "security.captcha_on_sign_in";
const ALLOW = "security.staff_ip_allowlist";
const CHOICES = ["off", "after_failures", "always"];
const pii = { makerspace_id: 7, viewer_is_superadmin: false, pii_visible: true, active: null, space_grants: [], recent: [] };

function respond(settings: unknown[], overrides: Record<string, unknown> = {}) {
  const payload = { makerspace_id: 7, settings, can_edit: true, can_lock: false, edited_as: "space", ...overrides };
  staffRequest.mockImplementation((path: string) => Promise.resolve(String(path).endsWith("/pii-access") ? pii : payload));
}
const patched = () => staffRequest.mock.calls.filter(([, init]) => init?.method === "PATCH").map(([, init]) => JSON.parse(init.body).values);

function renderPanel() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/admin/security"]}><SecuritySettingsPanel makerspace={{ id: 7, name: "Lab" } as Makerspace} /></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("SecuritySettingsPanel kinds", () => {
  it("edits a number within its range and refuses one looser than the lock", async () => {
    respond([row(SESSION, "int", 24, { lock: lock(48, "Insurer") })]);
    const { container } = renderPanel();
    const input = await screen.findByRole("spinbutton");
    expect(screen.getByText("Locked by platform, allows at most 48 hours: Insurer")).toBeInTheDocument();
    expect(screen.getByText("Now: 24 hours")).toBeInTheDocument();
    fireEvent.change(input, { target: { value: "72" } });
    expect(screen.getByRole("alert")).toHaveTextContent("The platform lock allows at most 48 hours.");
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "800" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Choose 1–720 hours.");
    fireEvent.change(input, { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patched()).toEqual([{ [SESSION]: 12 }]));
    await expectNoA11yViolations(container);
  });

  it("treats 0 as off for the idle timeout, which a lock never allows", async () => {
    respond([row(IDLE, "int", 30, { lock: lock(60) })]);
    renderPanel();
    fireEvent.change(await screen.findByRole("spinbutton"), { target: { value: "0" } });
    expect(screen.getByRole("alert")).toHaveTextContent("The platform lock allows at most 60 minutes.");
  });

  it("offers only choices at least as strict as the lock", async () => {
    respond([row(CAPTCHA, "choice", "always", { choices: CHOICES, lock: lock("after_failures") })]);
    renderPanel();
    const select = await screen.findByRole("combobox");
    expect(within(select).getByRole("option", { name: "Off" })).toBeDisabled();
    expect(within(select).getByRole("option", { name: "After failed attempts" })).toBeEnabled();
    expect(screen.getByText("Locked by platform, allows After failed attempts or stricter")).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "after_failures" } });
    await waitFor(() => expect(patched()).toEqual([{ [CAPTCHA]: "after_failures" }]));
  });

  it("edits the allow-list as network chips and keeps it inside the lock", async () => {
    respond([row(ALLOW, "list", ["10.1.0.0/16"], { lock: lock(["10.0.0.0/8"]) })]);
    const { container } = renderPanel();
    expect(await screen.findByText("10.1.0.0/16")).toBeInTheDocument();
    expect(screen.getByText("Locked by platform, allows only networks within 10.0.0.0/8")).toBeInTheDocument();
    const field = screen.getByRole("textbox", { name: /Add a network/ });
    fireEvent.change(field, { target: { value: "192.168.0.0/24" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The platform lock allows only networks within 10.0.0.0/8.");
    expect(screen.getByRole("button", { name: "Save list" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Remove 192.168.0.0/24" }));
    fireEvent.change(field, { target: { value: "10.2.3.0/24" } });
    fireEvent.keyDown(field, { key: "Enter" });
    fireEvent.click(screen.getByRole("button", { name: "Save list" }));
    await waitFor(() => expect(patched()).toEqual([{ [ALLOW]: ["10.1.0.0/16", "10.2.3.0/24"] }]));
    await expectNoA11yViolations(container);
  });

  it("lets a superadmin lock a number at its current value", async () => {
    respond([row(SESSION, "int", 24)], { can_lock: true, edited_as: "platform" });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Lock at current value" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      `/admin/makerspaces/7/security-settings/${encodeURIComponent(SESSION)}/lock`,
      { method: "PUT", body: JSON.stringify({ floor: 24, note: "" }) }));
  });
});

describe("security rules", () => {
  it("parses IPv4 and IPv6 networks and tells containment", () => {
    expect(parseCidr("10.1.2.3/16")).toEqual({ version: 4, base: 0x0a010000n, prefix: 16 });
    expect(parseCidr("2001:db8::/32")?.prefix).toBe(32);
    expect(parseCidr("203.0.113.9")?.prefix).toBe(32);
    for (const bad of ["10.0.0.0/33", "300.1.1.1", "1.2.3", "2001:db8::1::/64", "a/b/c", ""]) expect(parseCidr(bad)).toBeNull();
    expect(cidrWithin(parseCidr("10.2.0.0/24")!, parseCidr("10.0.0.0/8")!)).toBe(true);
    expect(cidrWithin(parseCidr("10.0.0.0/8")!, parseCidr("10.2.0.0/24")!)).toBe(false);
    expect(cidrWithin(parseCidr("2001:db8:1::/48")!, parseCidr("2001:db8::/32")!)).toBe(true);
    expect(cidrWithin(parseCidr("2001:db8::/32")!, parseCidr("10.0.0.0/8")!)).toBe(false);
  });

  it("an empty allow-list (any network) is looser than any locked list", () => {
    const setting = row(ALLOW, "list", [], { lock: lock(["10.0.0.0/8"]) }) as never;
    expect(strictnessProblem(setting, [])).toMatch(/only networks within 10.0.0.0\/8/);
    expect(strictnessProblem(setting, ["10.9.0.0/16"])).toBeNull();
  });
});
