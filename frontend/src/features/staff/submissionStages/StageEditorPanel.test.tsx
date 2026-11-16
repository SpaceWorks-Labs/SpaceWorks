import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { BLANK_RULES } from "./stageDraft";
import { StageEditorPanel } from "./StageEditorPanel";
import type { StagePlan } from "./types";

vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));

const plan: StagePlan = { event_id: 42, fingerprint: "a".repeat(64), timezone: "Asia/Kolkata", event_ends_at: "2026-12-31T00:00:00Z",
  stages: [{ ...BLANK_RULES, id: 7, position: 1, version: 1, name: "Submission", submissions: 3, pending_triage: 1,
    warnings: ["ambiguous_deadline_time"], extensions: [], shortlist: { applied_id: null, published: false, count: 0 } }],
  presets: [{ key: "full_pipeline", name: "Full pipeline", description: "Applications first.", requires_admission: true,
    stages: [{ name: "Idea", shortlist_after: true }, { name: "Prototype", required_link_kinds: ["repo"] }, { name: "Final" }] }],
  families: ["deck", "images"], link_kinds: ["repo", "video"], video_hosts: ["youtube"], field_types: ["short_text"],
  field_visibility: ["staff_and_judges"], max_stages: 10, answer_limits: {}, admission_enabled: false };

function renderPanel() {
  vi.mocked(staffRequest).mockReset().mockImplementation(async (_path, options) => (options?.method === "PUT" ? plan : plan) as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StageEditorPanel eventId={42} /></QueryClientProvider>);
  return client;
}

afterEach(() => vi.clearAllMocks());

describe("StageEditorPanel", () => {
  it("shows counts, the deadline warning and the time zone", async () => {
    renderPanel();
    expect(await screen.findByText("3 submitted · 1 waiting for triage")).toBeTruthy();
    expect(screen.getByText(/midnight or noon/)).toBeTruthy();
    expect(screen.getByText(/Asia\/Kolkata/)).toBeTruthy();
  });

  it("replaces the stages with a preset only after confirming, then saves the full plan", async () => {
    renderPanel();
    await screen.findByText("1. Submission");
    fireEvent.change(screen.getByLabelText("Start from a preset"), { target: { value: "full_pipeline" } });
    expect(screen.getByText("1. Submission")).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Replace stages" }));
    expect(screen.getByText("1. Idea")).toBeTruthy();
    expect(screen.getByText(/starts with applications/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Move Idea down" }));
    expect(screen.getByText("1. Prototype")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save stages" }));
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([, options]) => options?.method === "PUT")).toBe(true));
    const [path, options] = vi.mocked(staffRequest).mock.calls.find(([, o]) => o?.method === "PUT")!;
    expect(path).toBe("/admin/events/42/submission-stages/");
    const body = JSON.parse(String(options?.body));
    expect(body).toMatchObject({ expected_fingerprint: plan.fingerprint, preset: "full_pipeline" });
    expect(body.stages.map((s: { name: string }) => s.name)).toEqual(["Prototype", "Idea", "Final"]);
    expect(body.stages[2].shortlist_after).toBe(false);
    expect(options?.headers).toHaveProperty("Idempotency-Key", body.operation_id);
  });

  it("hides file controls for a links-only stage", async () => {
    renderPanel();
    const item = (await screen.findByText("1. Submission")).closest("li")!;
    expect(within(item).getByLabelText("Fewest files")).toBeTruthy();
    fireEvent.change(within(item).getByLabelText("What teams submit"), { target: { value: "links_only" } });
    expect(within(item).queryByLabelText("Fewest files")).toBeNull();
    expect(within(item).getByLabelText(/Most links/)).toBeTruthy();
  });
});
