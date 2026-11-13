import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../../../lib/api/errors";
import { notificationEventLabel } from "../../../../notifications/notificationEventLabels";
import { AdaptersScreen } from "./AdaptersScreen";
import { eta, openInterlocks, readings, temperatures } from "./AdapterStatus";
import type { AdapterSummary, BindingStatus } from "./adaptersApi";
import { WatchViewer, type WatchTransport } from "./WatchViewer";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));

const now = new Date().toISOString();
const adapter: AdapterSummary = { online: true, offline_since: null, id: "a1", name: "Workshop bridge", status: "active", last_seen_at: now, adapter_kind: "fdm_printer", vendor: "", software_version: "",
  capabilities: ["control", "job.dispatch", "locate.indicate", "locate.calibrate", "media.snapshot", "door.access", "checkout.kiosk"].map(name => ({ name })), config_version: 1, hello_at: now, bindings: [
    { id: "b1", target_type: "machine", machine_id: 7, target_id: "", external_ref: "", capabilities: ["control", "job.dispatch"], enabled: true,
      config: { max_session_minutes: 60 }, effective_config: { auto_off_idle_minutes: { value: 15, source: "type" }, max_session_minutes: { value: 60, source: "binding" }, require_area_clear: { value: true, source: "type" } },
      status: { state: "running", observed_at: now, progress_percent: 10, eta_seconds: 4800, telemetry: { temperatures: { nozzle: 215.5 } } } },
    { id: "b2", target_type: "storage_location", machine_id: null, target_id: "Shelf B2", external_ref: "", capabilities: ["locate.indicate", "locate.calibrate"], enabled: true, status: null },
    { id: "b3", target_type: "door", machine_id: null, target_id: "front", external_ref: "Front door", capabilities: ["media.snapshot", "door.access"], enabled: true, status: null },
    { id: "b4", target_type: "space", machine_id: null, target_id: "7", external_ref: "Entrance", capabilities: ["checkout.kiosk"], enabled: true, status: null }] };

function respond(overrides: Record<string, unknown> = {}) {
  staffRequest.mockImplementation(async (path: string, init?: { method?: string }) => {
    const key = `${init?.method ?? "GET"} ${path.split("?")[0]}`;
    if (key in overrides) { const value = overrides[key]; if (value instanceof Error) throw value; return value; }
    if (path.includes("/machine-service/board")) return { lanes: [{ machine_id: 7, running: [{ id: 5, title: "Bracket v2" }], queued: [] }] };
    if (path === "/admin/adapters/a1") return adapter;
    if (path.endsWith("/adapters")) return { results: [adapter] };
    if (path.includes("machine-types")) return path.endsWith("/adapter-profile") ? { machine_type_id: 3, config: { auto_off_idle_minutes: 15, require_area_clear: true }, updated_at: now } : { results: [{ id: 3, name: "FDM printer" }] };
    if (path.includes("/machines")) return { results: [{ id: 7, name: "Prusa MK4", is_active: true, machine_type: { id: 3 } }] };
    if (path.includes("/inventory")) return { results: [{ id: 1, name: "Drill", storage_location: "Shelf B2" }, { id: 2, name: "Saw", storage_location: "Shelf C1" }, { id: 3, name: "Clamp", storage_location: "Shelf D4" }] };
    if (path.endsWith("/poses")) return [{ id: "p1", binding: "b2", target_type: "storage_location", target_id: "Shelf B2", pose: { pan: 1 }, note: "", saved_by: 1, updated_at: now },
      { id: "p2", binding: "b2", target_type: "storage_location", target_id: "Shelf C1", pose: { pan: 2 }, note: "", saved_by: 1, updated_at: now }];
    if (path.endsWith("/events")) return [{ id: "e1", binding: "b1", operation_id: "", event_type: "job.progress", capability: "status", data: {}, observed_at: now, received_at: now }];
    if (path.endsWith("/printer-jobs") || path.includes("/printer-jobs?")) return { count: 0, next: null, previous: null, results: [] };
    if (path.endsWith("/webhook/deliveries")) return { results: [{ id: "d1", type: "job.queued", status: "dead", attempts: 6, last_status_code: 502, last_error: "bad gateway", created_at: now, delivered_at: null }] };
    if (path.endsWith("/webhook")) throw new StructuredApiError(404, { detail: "none" });
    return {};
  });
}
function show(url: string, switches = {}) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><AdaptersScreen makerspaceId={1} switches={{ access: true, video: true, recording: false, kiosk: true, ...switches }} onBack={vi.fn()} /></MemoryRouter>
  </QueryClientProvider>);
}
const base = "/m?view=adapters&adapter=a1";

describe("status formatting", () => {
  const status = (extra: Partial<BindingStatus>): BindingStatus => ({ state: "running", observed_at: 1_760_000_000, ...extra });
  it("reads temperatures and readings from telemetry and the ETA from eta_seconds", () => {
    expect(temperatures(status({ telemetry: { temperatures: { nozzle: 215, bed: 60 } } }))).toEqual([["nozzle", 215], ["bed", 60]]);
    expect(readings(status({ telemetry: { metrics: { fan: 80 } } }))).toEqual([["fan", 80]]);
    expect(temperatures(status({}))).toEqual([]);
    expect(eta(status({ eta_seconds: 20 }))).toBe("under a minute left");
    expect(eta(status({ eta_seconds: 2400 }))).toBe("about 40 min left");
    expect(eta(status({ eta_seconds: 5400 }))).toBe("about 1.5 hours left");
    expect(eta(status({}))).toBe("");
  });
  it("names only the interlocks that are not safe", () => {
    expect(openInterlocks(status({ interlocks: { enclosure_closed: false, estop_ok: true, filter_ok: false } }))).toEqual(["Enclosure open", "Filter needs attention"]);
    expect(openInterlocks(status({ interlocks: { enclosure_closed: null } }))).toEqual([]);
  });
  it("labels the adapter notification events", () => {
    expect(notificationEventLabel("adapter_attention")).toBe("Machine needs attention");
    expect(notificationEventLabel("adapter_access_denied")).toBe("Access denied at a device");
  });
});

describe("device adapters, second round", () => {
  beforeEach(() => { staffRequest.mockReset(); respond(); });

  it("shows the temperature, the ETA and the last-events disclosure", async () => {
    show(base);
    expect(await screen.findByText("215.5°C")).toBeVisible();
    expect(screen.getByText(/about 80 min left/)).toBeVisible();
    fireEvent.click(await screen.findByText("Last events"));
    expect(screen.getByText("job.progress")).toBeVisible();
  });

  it("walks the shelves one location at a time and skips the one without a saved position", async () => {
    show(`${base}&adapter_view=pointer`);
    fireEvent.click(await screen.findByRole("button", { name: "Walk the shelves" }));
    fireEvent.click((await screen.findAllByRole("button", { name: "Walk the shelves" })).at(-1)!);
    expect(await screen.findByText("Location 1 of 3")).toBeVisible();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b2/indicate",
      { method: "POST", body: JSON.stringify({ mode: "point", target_type: "storage_location", target_id: "Shelf B2", duration_seconds: 60 }) }));
    fireEvent.click(screen.getByRole("button", { name: "Next location" }));
    expect(await screen.findByText("Location 2 of 3")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Next location" }));
    expect(await screen.findByText("Location 3 of 3")).toBeVisible();
    expect(screen.getByText("No saved position. Calibrate it first.")).toBeVisible();
    expect(staffRequest.mock.calls.filter(([url]) => url === "/admin/adapter-bindings/b2/indicate")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Next location" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Walk the shelves" })).toHaveLength(2));
  });

  it("unlocks a door only after a confirmation that names the seconds", async () => {
    show(`${base}&adapter_view=status`);
    const group = await screen.findByRole("group", { name: "Controls for Front door" });
    fireEvent.change(within(group).getByLabelText("Unlock for"), { target: { value: "30" } });
    fireEvent.click(within(group).getByRole("button", { name: "Unlock door" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/The door opens for 30 seconds/)).toBeVisible();
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/adapter-bindings/b3/commands", expect.anything());
    fireEvent.click(within(dialog).getByRole("button", { name: "Unlock door" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b3/commands",
      { method: "POST", body: JSON.stringify({ capability: "door.access", command: "unlock", params: { seconds: 30 } }) }));
  });

  it("shows which safety values follow the type and which are overridden, and saves only the overrides", async () => {
    respond({ "PUT /admin/adapter-bindings/b1/config": { id: "b1", config: { auto_off_idle_minutes: 20, auto_apply_terminal: true }, effective_config: {} } });
    show(base);
    fireEvent.click((await screen.findAllByText("Safety settings"))[0]);
    expect(await screen.findByText("Follows the machine type (15)")).toBeVisible();
    expect(screen.getByText("Now: 60, overridden here")).toBeVisible();
    expect(screen.getByText("Now: 15, follows the machine type")).toBeVisible();
    const longest = screen.getByLabelText("Where the value for Longest session (minutes) comes from");
    expect(longest).toHaveValue("override");
    expect(screen.getByLabelText("Longest session (minutes)")).toHaveValue("60");
    fireEvent.change(longest, { target: { value: "inherit" } });
    fireEvent.change(screen.getByLabelText("Where the value for Switch off when idle for (minutes) comes from"), { target: { value: "override" } });
    fireEvent.change(screen.getByLabelText("Switch off when idle for (minutes)"), { target: { value: "20" } });
    fireEvent.click(screen.getByLabelText(/Apply clean results automatically/));
    fireEvent.click(screen.getByRole("button", { name: "Save safety settings" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b1/config",
      { method: "PUT", body: JSON.stringify({ auto_off_idle_minutes: 20, auto_apply_terminal: true }) }));
    expect(screen.getByText(/A failed report is always held for staff to review/)).toBeVisible();
  });

  it("sends a running job, lists this binding's jobs from its own route, filters by state, and approves a reported result", async () => {
    const job = { id: "j1", service_request_id: 5, service_request_name: "Bracket v2", machine_name: "Prusa", state: "reported", telemetry_state: "", progress_percent: 100, telemetry_at: null,
      outcome: "completed", actual_minutes: 30, percent_complete: null, failure_reason: "", reported_at: now, applied_at: null, created_at: now, command_status: "succeeded", command_attempts: 1, command_error: "" };
    respond({ "GET /admin/adapter-bindings/b1/jobs": { count: 1, next: null, previous: null, results: [job] },
      "POST /admin/adapter-bindings/b1/jobs": { job_id: "j2", state: "awaiting" }, "POST /admin/printer-jobs/j1/apply": { id: "j1", state: "applied" } });
    show(base);
    fireEvent.click((await screen.findAllByText("Jobs"))[0]);
    fireEvent.change(await screen.findByLabelText("Running job"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Send to adapter" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b1/jobs", { method: "POST", body: JSON.stringify({ service_request_id: 5 }) }));
    fireEvent.change(screen.getByLabelText("Show"), { target: { value: "needs_review" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b1/jobs?page=1&state=needs_review"));
    fireEvent.click(await screen.findByRole("button", { name: "Approve result" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/printer-jobs/j1/apply", expect.objectContaining({ method: "POST" })));
  });

  it("offers recording only with its switch, and explains retention", async () => {
    respond({ "POST /admin/adapter-bindings/b3/watch": { id: "w1", binding: "b3", status: "active", record: true, expires_at: new Date(Date.now() + 200_000).toISOString(), created_at: now, ended_at: null },
      "GET /member/adapter-watch/w1/signal": { signals: [], ice_servers: [] }, "GET /member/adapter-watch/w1/frame": { content_type: null, data: null } });
    const first = show(`${base}&adapter_view=watch`);
    await screen.findByRole("button", { name: "Start watching" });
    expect(screen.queryByText("Also record this watch")).toBeNull();
    first.unmount();
    show(`${base}&adapter_view=watch`, { recording: true });
    expect(await screen.findByText(/kept for 7 days, then deleted/)).toBeVisible();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Start watching and recording" }));
    expect(await screen.findByText("This watch is being recorded.")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b3/watch", { method: "POST", body: JSON.stringify({ record: true }) });
  });

  it("shows kiosk adapters and their bindings only with the kiosk switch", async () => {
    const view = show(`${base}&adapter_view=kiosk`);
    expect(await screen.findByText("Entrance")).toBeVisible();
    expect(screen.getByText(/The kiosk is only a terminal/)).toBeVisible();
    view.unmount();
    show(`${base}&adapter_view=kiosk`, { kiosk: false });
    await screen.findByText("Prusa MK4");
    expect(screen.queryByRole("tab", { name: "Kiosk" })).toBeNull();
  });

  it("shows the webhook secret once, after a rotation too, and lists deliveries", async () => {
    const hook = { url: "https://hooks.example.org/x", enabled: true, include_data: false, secret_version: 1, consecutive_failures: 0, disabled_at: null, disabled_reason: "", last_success_at: null };
    respond({ "GET /admin/adapters/a1/webhook": hook, "POST /admin/adapters/a1/webhook/rotate": { ...hook, secret: "whsec_second" } });
    show(`${base}&adapter_view=webhook`);
    expect(await screen.findByText("Gave up")).toBeVisible();
    expect(screen.getByText(/HTTP 502 · bad gateway/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Rotate secret" }));
    expect(screen.getByText(/The old secret stops working at once/)).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "Rotate secret" }).at(-1)!);
    expect(await screen.findByDisplayValue("whsec_second")).toBeVisible();
    expect(screen.getByText(/shown once and cannot be read again/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "I've copied it" }));
    expect(screen.queryByDisplayValue("whsec_second")).toBeNull();
  });

  it("creates a webhook with names-only opted in and reveals the secret on creation", async () => {
    respond({ "PUT /admin/adapters/a1/webhook": { url: "https://hooks.example.org/x", enabled: true, include_data: true, secret_version: 1, consecutive_failures: 0, disabled_at: null, disabled_reason: "", last_success_at: null, secret: "whsec_first" } });
    show(`${base}&adapter_view=webhook`);
    fireEvent.change(await screen.findByLabelText("Endpoint URL"), { target: { value: "https://hooks.example.org/x" } });
    fireEvent.click(screen.getByLabelText(/Include capability and command names/));
    fireEvent.click(screen.getByRole("button", { name: "Create webhook" }));
    expect(await screen.findByDisplayValue("whsec_first")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/adapters/a1/webhook", { method: "PUT", body: JSON.stringify({ url: "https://hooks.example.org/x", include_data: true }) });
  });

  it("explains a refused private URL and re-saves a self-disabled webhook to re-enable it", async () => {
    const off = { url: "https://hooks.example.org/x", enabled: false, include_data: true, secret_version: 2, consecutive_failures: 10, disabled_at: now, disabled_reason: "Too many failures.", last_success_at: null };
    respond({ "GET /admin/adapters/a1/webhook": off, "PUT /admin/adapters/a1/webhook": new StructuredApiError(400, { url: ["Enter a public https address."] }) });
    show(`${base}&adapter_view=webhook`);
    expect(await screen.findByText("This webhook switched itself off.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Re-enable/ }));
    expect(await screen.findByText("Enter a public https address.")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/adapters/a1/webhook", { method: "PUT", body: JSON.stringify({ url: off.url, include_data: true }) });
  });

  it("edits a machine type's safety defaults", async () => {
    respond({ "PUT /admin/makerspace/1/machine-types/3/adapter-profile": { machine_type_id: 3, config: {} } });
    show("/m?view=adapters&adapter_tab=types");
    fireEvent.click(await screen.findByText("FDM printer"));
    const idle = await screen.findByLabelText("Switch off when idle for (minutes)");
    await waitFor(() => expect(idle).toHaveValue("15"));
    fireEvent.change(screen.getByLabelText("Longest session (minutes)"), { target: { value: "120" } });
    fireEvent.click(screen.getByLabelText("Filter must be healthy before it starts"));
    fireEvent.click(screen.getByRole("button", { name: "Save defaults" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/1/machine-types/3/adapter-profile", { method: "PUT",
      body: JSON.stringify({ auto_off_idle_minutes: 15, max_session_minutes: 120, require_area_clear: true, require_filter_ok: true }) }));
  });
});

describe("live video", () => {
  const instances: FakePeer[] = [];
  class FakePeer {
    connectionState = "new";
    onicecandidate: ((event: { candidate: { toJSON: () => unknown } | null }) => void) | null = null;
    ontrack: ((event: { streams: unknown[]; track: unknown }) => void) | null = null;
    onconnectionstatechange: (() => void) | null = null;
    remote: unknown = null; added: unknown[] = []; closed = false; config: unknown;
    constructor(config: unknown) { this.config = config; instances.push(this); }
    addTransceiver = vi.fn();
    createOffer = async () => ({ type: "offer", sdp: "v=0 offer" });
    setLocalDescription = vi.fn(async () => undefined);
    setRemoteDescription = vi.fn(async (value: unknown) => { this.remote = value; });
    addIceCandidate = vi.fn(async (value: unknown) => { this.added.push(value); });
    close = () => { this.closed = true; };
  }
  beforeEach(() => { instances.length = 0; vi.stubGlobal("RTCPeerConnection", FakePeer); vi.stubGlobal("MediaStream", class { constructor(public tracks: unknown[]) {} }); });
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
  const transport = (over: Partial<WatchTransport> = {}): WatchTransport => ({ poll: vi.fn(async () => ({ signals: [], ice_servers: [{ urls: ["turn:t.example"], username: "u", credential: "c" }] })),
    signal: vi.fn(async () => ({ n: 1 })), frame: vi.fn(async () => ({ content_type: "image/jpeg", data: "QUJD" })), ...over });

  it("sends an offer, applies the answer and ICE, uses the server's TURN credentials, and closes on unmount", async () => {
    const tx = transport();
    vi.mocked(tx.poll).mockResolvedValueOnce({ signals: [], ice_servers: [{ urls: ["turn:t.example"], username: "u", credential: "c" }] })
      .mockResolvedValue({ signals: [{ n: 1, from: "adapter", kind: "answer", sdp: "v=0 answer", candidate: "" },
        { n: 2, from: "adapter", kind: "candidate", sdp: "", candidate: JSON.stringify({ candidate: "candidate:1 1 udp 1 1.2.3.4 5 typ host", sdpMid: "0" }) }], ice_servers: [] });
    const view = render(<WatchViewer transport={tx} label="Camera view" />);
    await waitFor(() => expect(tx.signal).toHaveBeenCalledWith({ kind: "offer", sdp: "v=0 offer" }));
    const peer = instances[0];
    expect(peer.config).toEqual({ iceServers: [{ urls: ["turn:t.example"], username: "u", credential: "c" }] });
    await waitFor(() => expect(peer.remote).toEqual({ type: "answer", sdp: "v=0 answer" }), { timeout: 3000 });
    await waitFor(() => expect(peer.added).toHaveLength(1));
    act(() => { peer.onicecandidate?.({ candidate: { toJSON: () => ({ candidate: "local" }) } }); });
    expect(tx.signal).toHaveBeenCalledWith({ kind: "candidate", candidate: JSON.stringify({ candidate: "local" }) });
    act(() => { peer.ontrack?.({ streams: [{}], track: {} }); });
    expect(await screen.findByText("Live")).toBeVisible();
    view.unmount();
    expect(peer.closed).toBe(true);
  });

  it("falls back to refreshing stills when the peer connection fails", async () => {
    const tx = transport();
    render(<WatchViewer transport={tx} label="Camera view" />);
    await waitFor(() => expect(instances.length).toBe(1));
    act(() => { instances[0].connectionState = "failed"; instances[0].onconnectionstatechange?.(); });
    const image = await screen.findByRole("img", { name: "Camera view" });
    expect(image).toHaveAttribute("src", "data:image/jpeg;base64,QUJD");
    expect(screen.getByText(/refreshes every few seconds/)).toBeVisible();
    expect(instances[0].closed).toBe(true);
  });

  it("uses stills straight away where WebRTC does not exist", async () => {
    vi.stubGlobal("RTCPeerConnection", undefined);
    const tx = transport();
    render(<WatchViewer transport={tx} label="Camera view" />);
    expect(await screen.findByRole("img", { name: "Camera view" })).toBeVisible();
    expect(tx.signal).not.toHaveBeenCalled();
  });
});
