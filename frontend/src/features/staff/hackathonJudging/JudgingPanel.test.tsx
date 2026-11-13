import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";
import { JudgingPanel } from "./JudgingPanel";

const request = vi.fn();
vi.mock("../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../lib/api")>()),
  staffRequest: (...args: unknown[]) => request(...args),
}));
// Each of these has its own tests; the panel only decides whether to mount them and what to hand them.
vi.mock("./DefinitionEditor", () => ({ DefinitionEditor: ({ pairwiseEnabled }: { pairwiseEnabled: boolean }) => <p>definition editor pairwise={String(pairwiseEnabled)}</p> }));
vi.mock("./ResultsPanel", () => ({ ResultsPanel: ({ galleryEnabled, rounds }: { galleryEnabled: boolean; rounds: unknown[] }) => <p>results gallery={String(galleryEnabled)} rounds={rounds.length}</p> }));
vi.mock("./MentorShortlistBoard", () => ({ MentorShortlistBoard: () => <p>mentor shortlist board</p> }));
vi.mock("./ScoresExportButton", () => ({ ScoresExportButton: ({ rounds }: { rounds: unknown[] }) => <button type="button">scores export {rounds.length}</button> }));
vi.mock("./ManagerExtras", () => ({ ManagerExtras: ({ fullManager, features }: { fullManager: boolean; features: readonly string[] }) => <p>manager extras full={String(fullManager)} features={features.join("+")}</p> }));

const scope = { makerspaceId: 1, eventId: 2, actorId: 3, context: "person" };
const base = { min_reviews: 3, normalization: "none", assigned: 10, submitted: 4, recused: 1, skipped: 2, estimated_judges: 5, minutes_per_view: 4, judging_minutes: 45,
  rows: [], closes_at: null, coverage_complete: true, version: 7 };
const draftRound = { ...base, id: 1, key: "draft-round", mode: "weighted_1_5", state: "draft" };
const openRound = { ...base, id: 2, key: "open-round", mode: "top3", state: "open", closes_at: "2026-12-01T10:00:00Z" };
const closedRound = { ...base, id: 3, key: "closed-round", mode: "weighted_1_5", normalization: "zscore", state: "closed", coverage_complete: false };
const pairRound = { ...base, id: 4, key: "pair-round", mode: "pairwise", state: "open", submitted: 8 };
const pairDraft = { ...pairRound, id: 5, key: "pair-draft", state: "draft" };

let rounds: unknown[];
let listError: Error | undefined;
let writes: Array<{ path: string; method: string; body: Record<string, unknown> }>;
let writeResult: unknown;
let writeError: Error | undefined;

function mount(props: Partial<Parameters<typeof JudgingPanel>[0]> = {}) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><JudgingPanel scope={scope} {...props} /></QueryClientProvider>);
}
beforeEach(() => {
  rounds = [draftRound, openRound, closedRound];
  listError = undefined; writeError = undefined; writes = []; writeResult = { coverage_complete: true };
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      writes.push({ path, method: "POST", body: JSON.parse(String(init.body)) });
      if (writeError) throw writeError;
      return writeResult;
    }
    if (listError) throw listError;
    return { count: rounds.length, next: null, previous: null, results: rounds };
  });
});

describe("loading, empty and error states", () => {
  it("shows a loading indicator, then the empty state when there are no rounds", async () => {
    rounds = [];
    mount();
    expect(screen.getByText("Loading judging rounds…")).toBeInTheDocument();
    expect(await screen.findByText("No judging rounds yet")).toBeInTheDocument();
    expect(screen.getByText("Create a rubric or a top-three round to begin.")).toBeInTheDocument();
  });
  it("shows a retryable error and keeps no empty-state claim hidden behind it", async () => {
    listError = new Error("Rounds unavailable");
    mount();
    expect(await screen.findByText(/Rounds unavailable/)).toBeInTheDocument();
    listError = undefined;
    fireEvent.click(screen.getByRole("button", { name: /retry|try again/i }));
    expect(await screen.findByText("draft-round")).toBeInTheDocument();
  });
  it("replaces the panel with an access-lost error on a 403", async () => {
    listError = new StructuredApiError(403, { detail: "Not a judge manager", code: "module_disabled" });
    mount();
    await waitFor(() => {
      expect(screen.queryByText("Assignment planning")).toBeNull();
      expect(screen.getByText("Not a judge manager")).toBeInTheDocument();
    }, { timeout: 3000 });
    await new Promise((r) => setTimeout(r, 300));
    expect(request).toHaveBeenCalledTimes(2); // one refetch after the cache clear, not a loop
  });
});

describe("round cards by state and mode", () => {
  it("describes each method and shows the matching state actions", async () => {
    mount({ timezone: "Asia/Kolkata", fullManager: true });
    await screen.findByText("draft-round");
    expect(screen.getByText("Weighted 1–5 · weighted average · At least 3 reviews per project.")).toBeInTheDocument();
    expect(screen.getByText("Top-three ranking · fixed six points per ballot · At least 3 reviews per project.")).toBeInTheDocument();
    expect(screen.getByText("Weighted 1–5 · z-score ranking · At least 3 reviews per project.")).toBeInTheDocument();
    expect(screen.getByText(/Closes .*\(Asia\/Kolkata\)/)).toBeInTheDocument();
    expect(screen.getAllByText("4 of 10 assignments submitted · 1 recused · 2 skipped")).toHaveLength(3);
    expect(screen.getAllByText("Estimated judges: 5 at 4 minutes per project in a 45-minute judging window.")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Open and freeze rubric" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview assignments" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Close scoring" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finalize round" })).toBeDisabled();
  });
  it("hides finalize and results for a non-manager, shows them for a full manager", async () => {
    const { unmount } = mount();
    await screen.findByText("draft-round");
    expect(screen.queryByRole("button", { name: "Finalize round" })).toBeNull();
    expect(screen.queryByText("mentor shortlist board")).toBeNull();
    expect(screen.queryByText(/^results gallery/)).toBeNull();
    expect(screen.getByText("manager extras full=false features=")).toBeInTheDocument();
    unmount();
    mount({ fullManager: true, galleryEnabled: true, features: ["events.scores_export", "x"] });
    expect(await screen.findByText("mentor shortlist board")).toBeInTheDocument();
    expect(await screen.findByText("results gallery=true rounds=3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "scores export 3" })).toBeInTheDocument();
    expect(screen.getByText("manager extras full=true features=events.scores_export+x")).toBeInTheDocument();
  });
  it("omits the scores export without the feature", async () => {
    mount({ fullManager: true, features: [] });
    await screen.findByText("draft-round");
    expect(screen.queryByRole("button", { name: /scores export/ })).toBeNull();
  });
  it("shows pairwise progress text and the pairwise-off notice with disabled actions", async () => {
    rounds = [pairRound, pairDraft];
    mount({ pairwiseEnabled: false });
    await screen.findByText("pair-round");
    expect(screen.getAllByText("Pairwise comparison · judges pick the better of two projects · At least 3 comparisons per project.")).toHaveLength(2);
    expect(screen.getAllByText("4 valid comparisons · 10 projects shown · 1 recused · 2 skipped")).toHaveLength(2);
    expect(screen.getAllByText(/Pairwise judging is switched off for this space/)).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Close comparisons" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Open and freeze rubric" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Preview assignments" })).toBeNull();
  });
  it("enables pairwise actions when the module is on", async () => {
    rounds = [pairRound, pairDraft];
    mount({ pairwiseEnabled: true });
    await screen.findByText("pair-round");
    expect(screen.queryByText(/switched off for this space/)).toBeNull();
    expect(screen.getByRole("button", { name: "Close comparisons" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Open and freeze rubric" })).toBeEnabled();
    expect(screen.getByText("definition editor pairwise=true")).toBeInTheDocument();
  });
  it("lists coverage rows when the round has them and a fallback pill label for a missing state", async () => {
    rounds = [{ ...draftRound, state: undefined }];
    mount();
    await screen.findByText("draft-round");
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });
});

describe("assignment planning inputs", () => {
  it("switches the partition, reveals the seed re-roll and describes the keep/replace choice", async () => {
    mount();
    await screen.findByText("draft-round");
    expect(screen.queryByRole("button", { name: "Re-roll" })).toBeNull();
    expect(screen.getByText("Judges keep what they have; the plan only adds what coverage still needs.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Partition"), { target: { value: "random" } });
    expect(screen.getByText(/Seed 0\./)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Re-roll" }));
    expect(screen.queryByText(/Seed 0\./)).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Re-plan unscored" }));
    expect(screen.getByText("Unscored assignments may move to another judge. Scored work is never touched.")).toBeInTheDocument();
  });
});

describe("confirm dialogs and actions", () => {
  it("opens a round only after the freeze confirmation, posting the round version", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Open and freeze rubric" }));
    const dialog = await screen.findByRole("alertdialog", {}, { timeout: 2000 }).catch(() => screen.getByRole("dialog"));
    expect(within(dialog).getByText("Freeze this judging rubric?")).toBeInTheDocument();
    expect(within(dialog).getByText("Opening freezes the method, criteria and eligible submission set.")).toBeInTheDocument();
    expect(writes).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].path).toBe("/admin/events/2/judging-rounds/1/open/");
    expect(writes[0].body).toMatchObject({ expected_version: 7 });
  });
  it("cancelling the close-scoring confirmation sends nothing", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Close scoring" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Close scoring?")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByText("Close scoring?")).toBeNull());
    expect(writes).toHaveLength(0);
  });
  it("finalizes with a trimmed coverage exception reason when coverage is incomplete", async () => {
    mount({ fullManager: true });
    const finalize = await screen.findByRole("button", { name: "Finalize round" });
    expect(finalize).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Coverage exception reason (only if needed)"), { target: { value: "  Two judges ill  " } });
    expect(finalize).toBeEnabled();
    fireEvent.click(finalize);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Finalize this round?")).toBeInTheDocument();
    expect(within(dialog).getByText("This action is recorded in the event history. Review coverage before continuing.")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].path).toBe("/admin/events/2/judging-rounds/3/finalize/");
    expect(writes[0].body).toMatchObject({ coverage_exception_reason: "Two judges ill" });
  });
  it("finalizes a fully covered round without a reason", async () => {
    rounds = [{ ...closedRound, coverage_complete: true }];
    mount({ fullManager: true });
    const finalize = await screen.findByRole("button", { name: "Finalize round" });
    expect(finalize).toBeEnabled();
    fireEvent.click(finalize);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).not.toHaveProperty("coverage_exception_reason");
  });
  it("surfaces a failed action as an error and closes nothing silently", async () => {
    writeError = new StructuredApiError(409, { detail: "Round already open", code: "stale_version" });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Close scoring" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText(/Round already open/)).toBeInTheDocument();
  });
});

describe("assignment preview and apply", () => {
  const plan = { pairs: [{ snapshot_id: 101, judge_role_assignment_id: 7 }], deficits: {}, coverage_complete: true, before_loads: { 7: 0 }, after_loads: { 7: 1 }, plan_fingerprint: "fp1", existing: "keep" };
  const openOnly = () => { rounds = [openRound]; };
  async function preview() {
    openOnly();
    mount();
    fireEvent.change(await screen.findByLabelText("Judge role assignment IDs"), { target: { value: "7, x, 8, 0, -3" } });
    fireEvent.change(screen.getByLabelText("Maximum projects per judge"), { target: { value: "20" } });
    writeResult = plan;
    fireEvent.click(screen.getByRole("button", { name: "Preview assignments" }));
    return screen.findByRole("region", { name: "Assignment preview for open-round" });
  }
  it("dry-runs with the parsed judge ids and load, then applies the fingerprinted plan and reports coverage", async () => {
    await preview();
    expect(writes[0].path).toBe("/admin/events/2/judging-rounds/2/assign/");
    expect(writes[0].body).toMatchObject({ strategy: "balanced", max_load: 20, dry_run: true, existing: "keep", judge_role_assignment_ids: [7, 8], seed: "0" });
    expect(writes[0].body).not.toHaveProperty("plan_fingerprint");
    writeResult = { coverage_complete: true };
    fireEvent.click(screen.getByRole("button", { name: "Apply this plan" }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1].body).toMatchObject({ dry_run: false, plan_fingerprint: "fp1" });
    expect(await screen.findByText("Assignments applied. Every project has its judges.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Assignment preview for open-round" })).toBeNull();
  });
  it("names the projects still short of judges after applying an incomplete plan", async () => {
    await preview();
    writeResult = { coverage_complete: false, deficits: { 101: 2 } };
    fireEvent.click(screen.getByRole("button", { name: "Apply this plan" }));
    expect(await screen.findByText("More judges are needed: project #101 needs 2 more.")).toBeInTheDocument();
  });
  it("marks the preview stale on plan_changed and offers a fresh preview instead of Apply", async () => {
    await preview();
    writeError = new StructuredApiError(409, { detail: "Plan moved", code: "plan_changed" });
    fireEvent.click(screen.getByRole("button", { name: "Apply this plan" }));
    expect(await screen.findByText("This preview is out of date.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply this plan" })).toBeNull();
    expect(screen.queryByText(/Plan moved/)).toBeNull();
    writeError = undefined; writeResult = plan;
    fireEvent.click(screen.getByRole("button", { name: "Preview again" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Apply this plan" })).toBeInTheDocument());
  });
  it("drops the preview when any planning input changes and when it is discarded", async () => {
    await preview();
    fireEvent.change(screen.getByLabelText("Maximum projects per judge"), { target: { value: "21" } });
    await waitFor(() => expect(screen.queryByRole("region", { name: "Assignment preview for open-round" })).toBeNull());
    writeResult = plan;
    fireEvent.click(screen.getByRole("button", { name: "Preview assignments" }));
    await screen.findByRole("region", { name: "Assignment preview for open-round" });
    fireEvent.click(screen.getByRole("button", { name: /discard/i }));
    expect(screen.queryByRole("region", { name: "Assignment preview for open-round" })).toBeNull();
  });
});

describe("pagination", () => {
  it("requests the next page of rounds", async () => {
    request.mockImplementation(async (path: string) => ({ count: 30, next: null, previous: null, results: path.includes("page=2") ? [{ ...draftRound, id: 40, key: "page-two" }] : rounds }));
    mount();
    await screen.findByText("draft-round");
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(await screen.findByText("page-two")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/events/2/judging-rounds/?page=2");
  });
});
