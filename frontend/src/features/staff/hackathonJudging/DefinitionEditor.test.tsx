import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";
import { DefinitionEditor } from "./DefinitionEditor";

const request = vi.fn();
vi.mock("../../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../lib/api")>()),
  staffRequest: (...args: unknown[]) => request(...args),
}));

const scope = { makerspaceId: 1, eventId: 2, actorId: 3, context: "person" };
const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const track = { id: 11, version: 2, name: "Hardware", description: "Boards", capacity: 5 };
const prize = { id: 21, version: 3, name: "Best build", description: "Top", award_count: 2, track_id: 11, sponsor_id: null, winner_selection_mode: "manager", amount_per_winner: "100.00" };
const criterion = { key: "craft", label: "Craft", weight: "2.0000", anchors: { "1": "a", "2": "b", "3": "c", "4": "d", "5": "e" } };
const round = { id: 31, version: 5, key: "round-1", mode: "weighted_1_5", min_reviews: 3, normalization: "zscore", opens_at: "2026-12-01T09:00:00Z", closes_at: null,
  minutes_per_view: 4, judging_minutes: 45, visibility: "all", fresh_eyes: true, panel: [7, 8], state: "draft", criteria: [criterion], share_feedback: true, judge_reminders: false, submission_stage_id: null };
const pairwise = { ...round, id: 32, key: "pw", mode: "pairwise", guidance: "Which is stronger?", exploration: 0.2, criteria: [], state: "open" };

type Data = { tracks: unknown[]; prizes: unknown[]; rounds: unknown[]; stages: unknown[] };
let data: Data;
let failWith: Error | undefined;
let writes: Array<{ path: string; method: string; body: Record<string, unknown> }>;

function mount(props: Partial<Parameters<typeof DefinitionEditor>[0]> = {}) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><DefinitionEditor scope={scope} {...props} /></QueryClientProvider>);
}
const kindSelect = () => screen.getByLabelText("Definition type");
const pick = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  data = { tracks: [track], prizes: [prize], rounds: [round, pairwise], stages: [] };
  failWith = undefined; writes = [];
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") {
      writes.push({ path, method: init.method, body: JSON.parse(String(init.body)) });
      if (failWith) throw failWith;
      return { id: 99, version: 6 };
    }
    if (path.includes("/tracks/")) return page(data.tracks);
    if (path.includes("/prizes/")) return page(data.prizes);
    if (path.includes("/judging-rounds/")) return page(data.rounds);
    if (path.includes("submission-stages")) return { stages: data.stages };
    return {};
  });
});

describe("DefinitionEditor tracks", () => {
  it("creates a new track with name, description and capacity as a POST", async () => {
    mount();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Software" } });
    fireEvent.change(screen.getByLabelText("Public description"), { target: { value: "Apps" } });
    fireEvent.change(screen.getByLabelText("Track capacity (0 means unlimited)"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    expect(await screen.findByText("Definition saved.")).toBeInTheDocument();
    expect(writes[0]).toMatchObject({ path: "/admin/events/2/tracks/", method: "POST" });
    expect(writes[0].body).toMatchObject({ name: "Software", description: "Apps", capacity: 12, expected_version: 0 });
  });
  it("loads a track, PATCHes only changed fields with its version, and reports no-change without a request", async () => {
    mount();
    await screen.findByRole("option", { name: "Hardware" });
    pick("Create or edit", "11");
    expect(screen.getByLabelText("Name")).toHaveValue("Hardware");
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    expect(await screen.findByText("No changes to save.")).toBeInTheDocument();
    expect(writes).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Track capacity (0 means unlimited)"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ path: "/admin/events/2/tracks/11/", method: "PATCH" });
    expect(writes[0].body).toMatchObject({ capacity: 9, expected_version: 2 });
    expect(writes[0].body).not.toHaveProperty("name");
    expect(await screen.findByText("Definition saved.")).toBeInTheDocument();
  });
  it("choosing Create new clears the loaded record", async () => {
    mount();
    await screen.findByRole("option", { name: "Hardware" });
    pick("Create or edit", "11");
    pick("Create or edit", "0");
    expect(screen.getByLabelText("Name")).toHaveValue("");
  });
});

describe("DefinitionEditor save failures", () => {
  it("shows the typed error, keeps the edits, and reloads the saved definition on request", async () => {
    failWith = new StructuredApiError(409, { detail: "Definition changed", code: "version_conflict" });
    mount();
    await screen.findByRole("option", { name: "Hardware" });
    pick("Create or edit", "11");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Mine" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    expect(await screen.findByText(/Definition changed/)).toBeInTheDocument();
    expect(screen.getByText("Your edits are still here. Review the saved version before reapplying a changed definition.")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Mine");
    fireEvent.click(screen.getByRole("button", { name: "Discard my edits and reload the saved definition" }));
    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveValue("Hardware"));
  });
  it("reloads a prize and a round the same way", async () => {
    failWith = new Error("boom");
    mount();
    fireEvent.change(kindSelect(), { target: { value: "prizes" } });
    await screen.findByRole("option", { name: "Best build" });
    pick("Create or edit", "21");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "X" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    fireEvent.click(await screen.findByRole("button", { name: "Discard my edits and reload the saved definition" }));
    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveValue("Best build"));
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    await screen.findByRole("option", { name: "round-1" });
    pick("Create or edit", "31");
    fireEvent.change(screen.getByLabelText("Round key"), { target: { value: "renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    fireEvent.click(await screen.findByRole("button", { name: "Discard my edits and reload the saved definition" }));
    await waitFor(() => expect(screen.getByLabelText("Round key")).toHaveValue("round-1"));
  });
  it("shows a list-load error from the server", async () => {
    request.mockImplementation(async () => { throw new StructuredApiError(403, { detail: "No judging access", code: "module_disabled" }); });
    mount();
    expect(await screen.findAllByText(/No judging access/)).not.toHaveLength(0);
  });
});

describe("DefinitionEditor prizes", () => {
  it("loads a prize with its amount and track, then submits the typed prize payload for a new one", async () => {
    mount();
    fireEvent.change(kindSelect(), { target: { value: "prizes" } });
    await screen.findByRole("option", { name: "Best build" });
    pick("Create or edit", "21");
    expect(screen.getByLabelText("Award slots")).toHaveValue(2);
    expect(screen.getByLabelText("Track")).toHaveValue("11");
    expect(screen.getByLabelText("Prize amount per winner (optional)")).toHaveValue("100.00");
    pick("Create or edit", "0");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Judges pick" } });
    fireEvent.change(screen.getByLabelText("Award slots"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Sponsor ID (optional)"), { target: { value: "6" } });
    fireEvent.click(screen.getByLabelText("Allow the assigned sponsor to propose a winner"));
    fireEvent.change(screen.getByLabelText("Prize amount per winner (optional)"), { target: { value: " 50 " } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ path: "/admin/events/2/prizes/", method: "POST" });
    expect(writes[0].body).toMatchObject({ name: "Judges pick", award_count: 3, sponsor_id: 6, winner_selection_mode: "sponsor_proposal", amount_per_winner: "50" });
  });
  it("sends a null amount and manager selection when nothing is filled", async () => {
    mount();
    fireEvent.change(kindSelect(), { target: { value: "prizes" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Plain" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).toMatchObject({ amount_per_winner: null, track_id: null, sponsor_id: null, winner_selection_mode: "manager" });
  });
});

describe("DefinitionEditor judging rounds", () => {
  it("shows weighted-rubric controls and edits criteria (add up to the limit, remove)", async () => {
    mount();
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    expect(screen.getByLabelText("Scoring method")).toHaveValue("weighted_1_5");
    expect(screen.getByRole("group", { name: "Criterion 1" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove criterion/ })).toBeNull();
    const add = screen.getByRole("button", { name: /Add criterion/ });
    fireEvent.click(add);
    expect(screen.getByRole("group", { name: "Criterion 2" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Remove criterion 1/ }));
    expect(screen.queryByRole("group", { name: "Criterion 2" })).toBeNull();
    for (let n = 0; n < 40; n += 1) { if (!(add as HTMLButtonElement).disabled) fireEvent.click(add); }
    expect(add).toBeDisabled();
    expect(screen.getAllByLabelText("Criterion key")).toHaveLength(30);
  });
  it("loads a round, shows its settings and sends only changed fields with UTC datetimes", async () => {
    mount();
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    await screen.findByRole("option", { name: "round-1" });
    pick("Create or edit", "31");
    expect(screen.getByLabelText("Round key")).toHaveValue("round-1");
    expect(screen.getByLabelText("What judges see")).toHaveValue("all");
    expect(screen.getByLabelText("Judge panel (optional)")).toHaveValue("7, 8");
    expect(screen.getByLabelText("Opens at (UTC, optional)")).toHaveValue("2026-12-01T09:00");
    expect(screen.getByLabelText("Closes at (UTC, optional)")).toHaveValue("");
    expect(screen.getByLabelText("Final ranking normalization")).toHaveValue("zscore");
    expect(screen.queryByLabelText("Public description")).toBeNull();
    fireEvent.change(screen.getByLabelText("Closes at (UTC, optional)"), { target: { value: "2026-12-02T10:30" } });
    fireEvent.change(screen.getByLabelText("Required nonconflicted reviews per project"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ path: "/admin/events/2/judging-rounds/31/", method: "PATCH" });
    expect(writes[0].body).toMatchObject({ closes_at: "2026-12-02T10:30:00Z", min_reviews: 5, expected_version: 5 });
    expect(writes[0].body).not.toHaveProperty("opens_at");
  });
  it("creates a top-three round with no criteria and forces normalization none", async () => {
    mount();
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    fireEvent.change(screen.getByLabelText("Round key"), { target: { value: "finals" } });
    fireEvent.change(screen.getByLabelText("Final ranking normalization"), { target: { value: "zscore" } });
    pick("Scoring method", "top3");
    expect(screen.queryByLabelText("Final ranking normalization")).toBeNull();
    expect(screen.queryByRole("group", { name: "Anchored rubric" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).toMatchObject({ key: "finals", mode: "top3", normalization: "none", opens_at: null, closes_at: null, submission_stage_id: null });
    expect(writes[0].body).not.toHaveProperty("criteria");
  });
  it("offers pairwise only when enabled; an existing pairwise round stays selectable but disabled when off", async () => {
    const { unmount } = mount();
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    expect(screen.queryByRole("option", { name: "Pairwise comparison" })).toBeNull();
    unmount();
    mount({ pairwiseEnabled: true });
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    expect(screen.getByRole("option", { name: "Pairwise comparison" })).toBeEnabled();
  });
  it("loads a pairwise round with its guidance and exploration, and saves them", async () => {
    mount();
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    await screen.findByRole("option", { name: "pw" });
    pick("Create or edit", "32");
    expect(screen.getByRole("option", { name: "Pairwise comparison" })).toBeDisabled();
    expect(screen.getByText(/Judges see one project at a time/)).toBeInTheDocument();
    expect(screen.getByLabelText("What “better” means (shown to judges)")).toHaveValue("Which is stronger?");
    expect(screen.getByText("Random picks: 20%")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Anchored rubric" })).toBeNull();
    fireEvent.change(screen.getByLabelText(/Random picks:/), { target: { value: "0.3" } });
    fireEvent.change(screen.getByLabelText("What “better” means (shown to judges)"), { target: { value: "Cleaner" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).toMatchObject({ guidance: "Cleaner", exploration: "0.30", expected_version: 5 });
  });
  it("offers the submission stage choice when the event has stages and locks it once the round is open", async () => {
    data.stages = [{ id: 1, position: 1, name: "Idea" }, { id: 2, position: 2, name: "Demo" }];
    mount();
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    const stage = await screen.findByLabelText("Stage this round judges");
    expect(stage).toBeEnabled();
    expect(within(stage).getByRole("option", { name: "Stage 2: Demo" })).toBeInTheDocument();
    await screen.findByRole("option", { name: "pw" });
    pick("Create or edit", "32");
    expect(screen.getByLabelText("Stage this round judges")).toBeDisabled();
    expect(screen.getByText("Fixed once the round opens.")).toBeInTheDocument();
  });
  it("round settings checkboxes and panel feed the payload", async () => {
    mount();
    fireEvent.change(kindSelect(), { target: { value: "judging-rounds" } });
    fireEvent.change(screen.getByLabelText("Round key"), { target: { value: "r" } });
    pick("What judges see", "all");
    fireEvent.click(screen.getByLabelText(/Fresh eyes/));
    fireEvent.click(screen.getByLabelText(/Share judges' team feedback/));
    fireEvent.click(screen.getByLabelText(/Remind judges with unfinished/));
    fireEvent.change(screen.getByLabelText("Judge panel (optional)"), { target: { value: "4, x, 9, -2" } });
    fireEvent.change(screen.getByLabelText("Criterion label"), { target: { value: "Craft" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).toMatchObject({ visibility: "all", fresh_eyes: true, share_feedback: true, judge_reminders: true, panel: [4, 9] });
  });
});

describe("DefinitionEditor busy state", () => {
  it("shows Saving… and disables the type picker while the save is in flight", async () => {
    let release: (value: unknown) => void = () => undefined;
    mount();
    request.mockImplementation((_path: string, init?: RequestInit) => init?.method === "POST" ? new Promise((resolve) => { release = resolve; }) : Promise.resolve(page([])));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Slow" } });
    fireEvent.click(screen.getByRole("button", { name: "Save definition" }));
    expect(await screen.findByRole("button", { name: /Saving…/ })).toBeDisabled();
    expect(kindSelect()).toBeDisabled();
    release({ id: 1, version: 1 });
    expect(await screen.findByText("Definition saved.")).toBeInTheDocument();
  });
});
