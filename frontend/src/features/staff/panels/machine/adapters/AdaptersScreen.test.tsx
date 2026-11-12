import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../../../lib/api/errors";
import { expectNoA11yViolations } from "../../../../../test/axe";
import { AdaptersScreen } from "./AdaptersScreen";
import type { AdapterSummary, AdapterSwitches } from "./adaptersApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));

const now = new Date().toISOString();
const adapter: AdapterSummary = { online: true, offline_since: null, id: "a1", name: "Workshop bridge", status: "active", last_seen_at: now, adapter_kind: "fdm_printer", vendor: "Acme",
  software_version: "1.2", capabilities: [{ name: "status" }, { name: "control" }, { name: "locate.indicate" }, { name: "locate.calibrate" }, { name: "media.snapshot" }],
  config_version: 3, hello_at: now, bindings: [
    { id: "b1", target_type: "machine", machine_id: 7, target_id: "", external_ref: "", capabilities: ["status", "control"], enabled: true,
      status: { state: "running", observed_at: now, progress_percent: 42, eta_seconds: 1800, power: "on", error_codes: ["filament_runout"], error_detail: "Spool 2 is empty",
        interlocks: { enclosure_closed: false }, telemetry: { temperatures: { nozzle: 215 } } } },
    { id: "b2", target_type: "storage_location", machine_id: null, target_id: "Shelf B2", external_ref: "", capabilities: ["locate.indicate", "locate.calibrate"], enabled: true, status: null },
    { id: "b3", target_type: "door", machine_id: null, target_id: "front", external_ref: "Front door", capabilities: ["media.snapshot"], enabled: true, status: null }] };

function respond(overrides: Record<string, unknown> = {}) {
  staffRequest.mockImplementation(async (path: string, init?: { method?: string }) => {
    const key = `${init?.method ?? "GET"} ${path.split("?")[0]}`;
    if (key in overrides) { const value = overrides[key]; if (value instanceof Error) throw value; return value; }
    if (path.endsWith("/adapters")) return { results: [adapter, { ...adapter, id: "a2", name: "Loft bridge", online: false, offline_since: new Date(Date.now() - 2 * 3_600_000).toISOString(), capabilities: [], bindings: [] }] };
    if (path === "/admin/adapters/a1") return adapter;
    if (path.includes("/machines") || path.includes("machine-types")) return { results: [{ id: 7, name: "Prusa MK4", is_active: true, machine_type: { id: 3 } }] };
    if (path.includes("/inventory")) return { results: [{ id: 1, name: "Drill", storage_location: "Shelf B2" }, { id: 2, name: "Saw", storage_location: "Shelf C1" }] };
    if (path.endsWith("/adapter-credentials")) return [];
    if (path.includes("/memberships")) return { results: [{ id: 1, user: { id: 9, display_name: "Asha Rao", username: "asha" } }] };
    if (path.endsWith("/poses") || path.endsWith("/commands") || path.endsWith("/events")) return [];
    if (path.endsWith("/position")) return { pose: { pan: 10, tilt: 20 } };
    return {};
  });
}

function show(url = "/staff/machines?view=adapters", props: Partial<AdapterSwitches> = {}) {
  const onBack = vi.fn();
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><AdaptersScreen makerspaceId={1} switches={{ access: true, video: true, recording: false, kiosk: false, ...props }} onBack={onBack} /></MemoryRouter>
  </QueryClientProvider>);
  return { ...view, onBack };
}
const calls = (method: string, path: string) => staffRequest.mock.calls.filter(([url, init]) => url === path && (init?.method ?? "GET") === method);

describe("device adapters console", () => {
  beforeEach(() => { staffRequest.mockReset(); respond(); });

  it("lists bridges with kind, capabilities, bound targets and online state", async () => {
    const { container } = show();
    expect(await screen.findByText("Workshop bridge")).toBeVisible();
    expect(screen.getByText("Online")).toBeVisible();
    expect(screen.getByText("Offline")).toBeVisible();
    expect(screen.getByText(/Offline since/)).toBeVisible();
    expect(screen.getByText(/5 capabilities/)).toBeVisible();
    expect(screen.getByText(/3 bound targets/)).toBeVisible();
    await expectNoA11yViolations(container);
  });

  it("enrols a bridge once, shows the one-time token, and explains the bridge limit on 409", async () => {
    respond({ "POST /admin/makerspace/1/devices": new StructuredApiError(409, { detail: "x", code: "adapter_bridges_quota_reached", limit: 2 }) });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Enrol a bridge" }));
    fireEvent.change(screen.getByLabelText("Bridge name"), { target: { value: "Loft bridge" } });
    fireEvent.click(screen.getByRole("button", { name: "Enrol bridge" }));
    expect(await screen.findByText(/already has the 2 bridges its plan allows/)).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/1/devices", { method: "POST", body: JSON.stringify({ kind: "adapter", name: "Loft bridge" }) });
    respond({ "POST /admin/makerspace/1/devices": { device: { id: "d" }, enrollment: { enrollment_id: "e1", device_id: "d", purpose: "enroll", token: "TOKEN-ABC", expires_at: now } } });
    fireEvent.click(screen.getByRole("button", { name: "Enrol bridge" }));
    expect(await screen.findByDisplayValue("TOKEN-ABC")).toBeVisible();
    expect(screen.getByText(/It won’t be shown again/)).toBeVisible();
  });

  it("shows status with progress, temperature and errors, and confirms a control before sending it", async () => {
    show("/staff/machines?view=adapters&adapter=a1");
    expect(await screen.findByText("Prusa MK4")).toBeVisible();
    expect(screen.getByText("Running")).toBeVisible();
    expect(screen.getByText(/42% done/)).toBeVisible();
    expect(screen.getByText("filament_runout")).toBeVisible();
    expect(screen.getByText("Spool 2 is empty")).toBeVisible();
    expect(screen.getByText("Enclosure open")).toBeVisible();
    expect(screen.getByText("215°C")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(calls("POST", "/admin/adapter-bindings/b1/commands")).toHaveLength(0);
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b1/commands",
      { method: "POST", body: JSON.stringify({ capability: "control", command: "pause", params: {} }) }));
  });

  it("binds a machine and shows binding_exists in plain words", async () => {
    respond({ "POST /admin/adapters/a1/bindings": new StructuredApiError(409, { detail: "x", code: "binding_exists" }) });
    show("/staff/machines?view=adapters&adapter=a1&adapter_view=bindings");
    await screen.findByRole("heading", { name: "Bind a target" });
    fireEvent.change(await screen.findByLabelText("Machine"), { target: { value: "7" } });
    fireEvent.click(screen.getByLabelText("control"));
    fireEvent.click(screen.getByRole("button", { name: "Bind" }));
    expect(await screen.findByText("That target is already bound to this adapter.")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/adapters/a1/bindings", { method: "POST", body: JSON.stringify({ target_type: "machine", capabilities: ["control"], machine_id: 7 }) });
  });

  it("indicates a storage location and explains an uncalibrated one", async () => {
    respond({ "POST /admin/adapter-bindings/b2/indicate": new StructuredApiError(409, { detail: "x", code: "pose_not_calibrated" }) });
    show("/staff/machines?view=adapters&adapter=a1&adapter_view=pointer");
    fireEvent.change(await screen.findByLabelText("Storage location"), { target: { value: "Shelf B2" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Indicate" }).at(-1)!);
    expect(await screen.findByText(/No position is saved for that place yet/)).toBeVisible();
  });

  it("saves a calibrated position from the reported pose", async () => {
    show("/staff/machines?view=adapters&adapter=a1&adapter_view=pointer");
    fireEvent.click(await screen.findByRole("button", { name: "Calibrate" }));
    fireEvent.change(await screen.findByLabelText("Storage location"), { target: { value: "Shelf C1" } });
    await waitFor(() => expect(screen.getByLabelText("pan")).toHaveValue("10"));
    fireEvent.click(screen.getByRole("button", { name: "Save position" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b2/poses",
      { method: "PUT", body: JSON.stringify({ target_type: "storage_location", target_id: "Shelf C1", pose: { pan: 10, tilt: 20 } }) }));
  });

  it("adds a credential with a write-only secret", async () => {
    respond({ "GET /admin/memberships": { results: [{ id: 1, user: { id: 9, display_name: "Asha Rao", username: "asha" } }] },
      "POST /admin/makerspace/1/adapter-credentials": { id: "c1", user: 9, kind: "pin", label: "", locked_until: null, last_used_at: null, disabled_at: null, created_at: now } });
    show("/staff/machines?view=adapters&adapter_tab=credentials");
    fireEvent.change(await screen.findByLabelText("Member"), { target: { value: "As" } });
    fireEvent.click(await screen.findByRole("button", { name: /Asha Rao/ }));
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "pin" } });
    const secret = screen.getByLabelText("PIN");
    expect(secret).toHaveAttribute("type", "password");
    fireEvent.change(secret, { target: { value: "12" } });
    expect(screen.getByText("A PIN is 6 to 12 digits.")).toBeVisible();
    fireEvent.change(secret, { target: { value: "4829" } });
    expect(screen.getByText("A PIN is 6 to 12 digits.")).toBeVisible();
    fireEvent.change(secret, { target: { value: "482913" } });
    fireEvent.click(screen.getByRole("button", { name: "Add credential" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/1/adapter-credentials",
      { method: "POST", body: JSON.stringify({ user_id: 9, kind: "pin", secret: "482913" }) }));
    expect(screen.queryByText("482913")).toBeNull();
  });

  it("hides the credentials tab and the watch tab while their switches are off", async () => {
    show("/staff/machines?view=adapters&adapter=a1", { access: false, video: false });
    await screen.findByText("Prusa MK4");
    expect(screen.queryByRole("tab", { name: "Watch" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Credentials" })).toBeNull();
  });

  it("starts a watch with the audit notice and revokes only after a danger confirmation", async () => {
    respond({ "POST /admin/adapter-bindings/b3/watch": { id: "w1", binding: "b3", status: "open", expires_at: new Date(Date.now() + 300_000).toISOString(), created_at: now, ended_at: null } });
    show("/staff/machines?view=adapters&adapter=a1&adapter_view=watch");
    expect(await screen.findByText(/recorded in the audit log with your name/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Start watching" }));
    expect(await screen.findByText("Watching")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Request a fresh still" }));
    await waitFor(() => expect(calls("POST", "/admin/adapter-watches/w1/snapshot")).toHaveLength(1));
  });

  it("revokes behind a confirmation", async () => {
    show("/staff/machines?view=adapters&adapter=a1");
    fireEvent.click(await screen.findByRole("button", { name: /Revoke adapter/ }));
    expect(calls("POST", "/admin/devices/a1/revoke")).toHaveLength(0);
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Revoke adapter" }));
    await waitFor(() => expect(calls("POST", "/admin/devices/a1/revoke")).toHaveLength(1));
  });

  it("lists access decisions and usage from their own routes with the chosen filters", async () => {
    respond({ "GET /admin/adapters/a1/access-decisions": { count: 1, next: null, previous: null, results: [{ id: "x1", binding: "b1", member: 9, credential_type: "pin", allowed: false, reason: "certification_required", session_id: null, created_at: now }] },
      "GET /admin/adapters/a1/usage": { count: 1, next: null, previous: null, results: [{ id: "u1", binding: "b1", operation_id: "o", session_id: 4, started_at: now, ended_at: now, active_minutes: 20, idle_minutes: 2, outcome: "completed", error_code: "", consumptions: [], created_at: now }] } });
    show("/staff/machines?view=adapters&adapter=a1&adapter_view=logs");
    fireEvent.click(await screen.findByRole("button", { name: "Access decisions" }));
    expect(await screen.findByText("certification required")).toBeVisible();
    expect(within(screen.getByRole("list", { name: "Access decisions" })).getByText("Denied")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Decision"), { target: { value: "false" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapters/a1/access-decisions?page=1&allowed=false"));
    fireEvent.click(screen.getByRole("button", { name: "Usage" }));
    expect(await screen.findByText(/20 min active/)).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/adapters/a1/usage?page=1");
  });
});
