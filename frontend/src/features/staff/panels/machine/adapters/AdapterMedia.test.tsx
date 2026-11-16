import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createRef, useState, type ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdapterDetail } from "./AdapterDetail";
import { AudioLive, AudioOptions } from "./AudioControls";
import type { AdapterSummary, AdapterSwitches, WatchAudio } from "./adaptersApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));

const now = new Date().toISOString();
const cache = { version: 1, entry_count: 7, issued_at: now, expires_at: new Date(Date.now() + 600_000).toISOString(), reconciled_at: null };
const adapter: AdapterSummary = { online: true, offline_since: null, id: "a1", name: "Door bridge", status: "active", last_seen_at: now, adapter_kind: "door", vendor: "Acme",
  software_version: "2.0", firmware: "1.4.2", health: "degraded", health_at: now, capabilities: [], config_version: 2, hello_at: now, bindings: [
    { id: "b1", target_type: "machine", machine_id: 7, target_id: "", external_ref: "Printer", enabled: true, status: null, offline_cache: cache,
      capabilities: ["status", "artifact.upload", "detection.report", "telemetry.history", "diagnostics", "access.cache"] }] };
const switches: AdapterSwitches = { access: true, video: true, recording: true, kiosk: false, artifacts: true, detections: true, history: true, diagnostics: true, offlineCache: true };

function show(view: string) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={[`/m?adapter_view=${view}`]}><AdapterDetail makerspaceId={1} adapterId="a1" switches={switches} onBack={() => undefined} /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, init?: { method?: string }) => {
    if (path === "/admin/adapters/a1") return adapter;
    if (path.includes("/machines")) return { results: [{ id: 7, name: "Prusa MK4", is_active: true, machine_type: { id: 3 } }] };
    if (path.includes("/detections")) return { count: 1, next: null, previous: null, results: [{ id: "d1", binding: "b1", kind: "fire", confidence: 0.91, artifact_id: null, note: "", observed_at: now }] };
    if (path.includes("/telemetry")) return { binding_id: "b1", series: ["temp.bed"], selected: path.includes("series=") ? "temp.bed" : "", resolution: 0,
      points: path.includes("series=") ? [{ ts: new Date(Date.now() - 60_000).toISOString(), avg: 60, min: 59, max: 61, n: 1 }, { ts: now, avg: 62, min: 61, max: 63, n: 1 }] : [] };
    if (path.includes("/artifacts")) return { count: 1, next: null, previous: null, results: [{ id: "x1", binding: "b1", kind: "timelapse", content_type: "video/mp4", size_bytes: 3_000_000, status: "ready",
      service_request_id: 12, session_id: null, captured_at: now, created_at: now, expires_at: now }] };
    if (path.includes("/artifact-url") || path.endsWith("/url")) return { url: "https://s.test/get", content_type: "video/mp4", kind: "timelapse" };
    if (path.includes("/config-versions")) return init?.method === "POST" ? { id: "c3", version: 3, config: {}, created_at: now, ack_outcome: "", ack_detail: "", acked_at: null }
      : [{ id: "c2", version: 2, config: {}, created_at: now, ack_outcome: "applied", ack_detail: "", acked_at: now }];
    if (path.includes("/log-bundle")) return { command_id: "k1", status: "queued" };
    return {};
  });
});

describe("adapter media and data views", () => {
  it("lists detections with a plain-language kind and says core never stops a machine", async () => {
    show("detections");
    expect(await screen.findByText("Fire")).toBeVisible();
    expect(screen.getByText("91% sure")).toBeVisible();
    expect(screen.getByText(/never stops a machine because of a detection/)).toBeVisible();
  });

  it("shows a timelapse as a private, retention-limited video", async () => {
    show("artifacts");
    expect(await screen.findByText(/Private\. Kept 30 days/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    await waitFor(() => expect(document.querySelector("video")?.getAttribute("src")).toBe("https://s.test/get"));
  });

  it("draws a telemetry chart for the chosen reading", async () => {
    show("telemetry");
    expect(await screen.findByRole("img", { name: /temp\.bed/ })).toBeInTheDocument();
    expect(screen.getByText("Showing every sample.")).toBeVisible();
  });

  it("shows health and firmware and asks for a log bundle", async () => {
    show("diagnostics");
    expect(await screen.findByText("Degraded")).toBeVisible();
    expect(screen.getByText("1.4.2")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Request log bundle" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapter-bindings/b1/log-bundle", { method: "POST" }));
    expect(await screen.findByText(/It appears below when the adapter uploads it/)).toBeVisible();
  });

  it("shows the offline cache as a count and an expiry, never a digest, and pushes a config version", async () => {
    show("offline");
    expect(await screen.findByText(/7 cards/)).toBeVisible();
    expect(await screen.findByText("Version 2")).toBeVisible();
    expect(await screen.findByText("Applied")).toBeVisible();
    fireEvent.change(screen.getByLabelText(/New config/), { target: { value: "not json" } });
    expect(screen.getByRole("button", { name: "Push new version" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/New config/), { target: { value: "{\"poll_seconds\": 30}" } });
    fireEvent.click(screen.getByRole("button", { name: "Push new version" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/adapters/a1/config-versions", { method: "POST", body: JSON.stringify({ config: { poll_seconds: 30 } }) }));
  });
});

function Harness({ canTalk = true, record = true, children }: { canTalk?: boolean; record?: boolean; children?: ReactNode }) {
  const [value, setValue] = useState<WatchAudio>({});
  return <>{children}<AudioOptions canListen canTalk={canTalk} canRecord record={record} value={value} onChange={setValue} /></>;
}

describe("audio controls", () => {
  it("asks for the audio-recording notice only when audio is on and recording was chosen", () => {
    render(<Harness />);
    expect(screen.queryByLabelText(/audio notice is displayed/)).toBeNull();
    fireEvent.click(screen.getByLabelText(/Listen to the device/));
    expect(screen.getByLabelText(/audio notice is displayed/)).toBeVisible();
    expect(screen.getByText(/deleted after 3 days/)).toBeVisible();
    expect(screen.getByText(/People near the device may hear this/)).toBeVisible();
  });

  it("push-to-talk signals only while the button is held and shows a clear indicator", async () => {
    const mic = createRef<MediaStreamTrack | null>() as { current: MediaStreamTrack | null };
    mic.current = { enabled: false } as MediaStreamTrack;
    render(<QueryClientProvider client={new QueryClient()}><AudioLive watchId="w1" talk muted={false} onMute={() => undefined} mic={mic} /></QueryClientProvider>);
    const button = screen.getByRole("button", { name: "Hold to talk" });
    fireEvent.pointerDown(button);
    expect(await screen.findByText("The device can hear you now.")).toBeVisible();
    expect(mic.current.enabled).toBe(true);
    fireEvent.pointerUp(screen.getByRole("button", { name: /Talking/ }));
    await waitFor(() => expect(mic.current?.enabled).toBe(false));
    expect(staffRequest.mock.calls.map(([path, init]) => [path, init.body])).toEqual([
      ["/member/adapter-watch/w1/talk", JSON.stringify({ active: true })], ["/member/adapter-watch/w1/talk", JSON.stringify({ active: false })]]);
  });
});
