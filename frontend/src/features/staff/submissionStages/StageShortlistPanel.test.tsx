import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { BLANK_RULES } from "./stageDraft";
import { publishWarning, StageShortlistPanel } from "./StageShortlistPanel";
import type { Shortlist } from "./types";

vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));

const shortlist: Shortlist = { stage_id: 7, label: "Shortlist", pending_triage: 0, candidates: 5, email_enabled: false,
  stage_entries: [{ submission_id: 1, team_id: 11, team_name: "Arm crew", snapshot_id: 21, triage: "eligible", submitted_at: null },
    { submission_id: 2, team_id: 12, team_name: "Plant crew", snapshot_id: 22, triage: "eligible", submitted_at: null }],
  current: { id: 3, selection: "manual", top_n: null, source_round_id: null, created_at: "2026-11-01T00:00:00Z", published_at: null,
    entries: [{ submission_id: 1, team_id: 11, snapshot_id: 21, title: "Robot arm", source_rank: null },
      { submission_id: 2, team_id: 12, snapshot_id: 22, title: "Plant bot", source_rank: null }] }, allowed_actions: ["apply", "publish"] };

describe("stage shortlist (S11)", () => {
  it("warns how many teams will not be told when the email is off", () => {
    expect(publishWarning({ not_shortlisted: 3, email_enabled: false })).toBe("3 teams will NOT be told by email that they were not shortlisted.");
    expect(publishWarning({ not_shortlisted: 1, email_enabled: false })).toMatch(/^1 team will NOT/);
    expect(publishWarning({ not_shortlisted: 3, email_enabled: true })).toBe("");
  });

  it("shows the warning and the inline email switch in the publish confirmation", async () => {
    vi.mocked(staffRequest).mockReset().mockImplementation(async path => {
      if (String(path).includes("/shortlist/")) return shortlist as never;
      if (String(path).includes("programme-options")) return { version: 2, shortlist_email: false } as never;
      return { count: 0, next: null, previous: null, results: [] } as never;
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><StageShortlistPanel eventId={42}
      stage={{ ...BLANK_RULES, id: 7, position: 1, version: 1, name: "Idea", shortlist_after: true }} /></QueryClientProvider>);
    expect(await screen.findByText("Robot arm")).toBeTruthy();
    expect(await screen.findByLabelText("Email teams their shortlist result when published")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Publish the shortlist" }));
    expect(await screen.findByText(/3 teams will NOT be told/)).toBeTruthy();
    client.clear();
  });

  it("promotes the next team in place of a withdrawn shortlisted team (S12)", async () => {
    const published: Shortlist = { ...shortlist, stage_entries: shortlist.stage_entries.slice(0, 1), allowed_actions: ["promote"],
      current: { ...shortlist.current!, selection: "top_n", source_round_id: 5, published_at: "2026-11-02T00:00:00Z" } };
    vi.mocked(staffRequest).mockReset().mockImplementation(async path => {
      if (String(path).includes("/shortlist/")) return published as never;
      if (String(path).includes("programme-options")) return { version: 2 } as never;
      return { count: 0, next: null, previous: null, results: [] } as never;
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><StageShortlistPanel eventId={42}
      stage={{ ...BLANK_RULES, id: 7, position: 1, version: 1, name: "Idea", shortlist_after: true }} /></QueryClientProvider>);
    fireEvent.change(await screen.findByLabelText("Withdrawn shortlisted team"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Promote next team" }));
    fireEvent.click(await screen.findByRole("button", { name: "Promote and publish" }));
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([path]) => String(path).endsWith("/shortlist/promote/"))).toBe(true));
    const [, options] = vi.mocked(staffRequest).mock.calls.find(([path]) => String(path).endsWith("/shortlist/promote/"))!;
    const body = JSON.parse(String(options?.body));
    expect(body).toMatchObject({ withdrawn_submission_id: 2 });
    expect(options?.headers).toHaveProperty("Idempotency-Key", body.operation_id);
    client.clear();
  });
});
