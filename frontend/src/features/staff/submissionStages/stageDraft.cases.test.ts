import { describe, expect, it } from "vitest";
import { StructuredApiError } from "../../../lib/api/errors";
import { blankStage, BLANK_RULES, cleanForMode, fromInput, fromPreset, fromSaved, modeAllows, move, saveBody, stageErrorMessage, toInput } from "./stageDraft";
import type { StageDraft } from "./types";

const row = (over: Partial<StageDraft> = {}): StageDraft => ({ ...BLANK_RULES, id: null, key: "k", ...over } as StageDraft);
const err = (code: string, body: Record<string, unknown> = {}) => new StructuredApiError(409, { code, ...body } as never);

describe("drafts", () => {
  it("gives each new draft a distinct local key and a positional name", () => {
    const a = blankStage(1), b = blankStage(2);
    expect(a.name).toBe("Stage 1");
    expect(b.name).toBe("Stage 2");
    expect(a.key).not.toBe(b.key);
    expect(a.id).toBeNull();
  });
  it("copies saved stages over the blank rules, keeping the id and ignoring unknown fields", () => {
    const [draft] = fromSaved([{ id: 7, name: "Final", deadline: "2026-05-01T10:00:00Z", extra: "dropped" } as never]);
    expect(draft).toMatchObject({ id: 7, name: "Final", deadline: "2026-05-01T10:00:00Z", min_files: 0, late_policy: "reject" });
    expect(draft).not.toHaveProperty("extra");
  });
  it("applies a preset with dates cleared and no reused ids", () => {
    const rows = fromPreset({ stages: [{ name: "One", opens_at: "x", deadline: "y", id: 4 }, { name: "Two" }] } as never);
    expect(rows.map(r => [r.name, r.opens_at, r.deadline, r.id])).toEqual([["One", null, null, null], ["Two", null, null, null]]);
    expect(new Set(rows.map(r => r.key)).size).toBe(2);
  });
});

describe("move", () => {
  const rows = [row({ name: "a" }), row({ name: "b" }), row({ name: "c" })];
  it("swaps with the neighbour", () => {
    expect(move(rows, 1, -1).map(r => r.name)).toEqual(["b", "a", "c"]);
    expect(move(rows, 1, 1).map(r => r.name)).toEqual(["a", "c", "b"]);
  });
  it("returns an unchanged copy at either edge", () => {
    const up = move(rows, 0, -1), down = move(rows, 2, 1);
    expect(up.map(r => r.name)).toEqual(["a", "b", "c"]);
    expect(down.map(r => r.name)).toEqual(["a", "b", "c"]);
    expect(up).not.toBe(rows);
  });
});

describe("modeAllows", () => {
  it.each([
    ["files_and_links", { files: true, links: true, minFiles: true, requiredKinds: true }],
    ["files_only", { files: true, links: false, minFiles: true, requiredKinds: false }],
    ["links_only", { files: false, links: true, minFiles: false, requiredKinds: true }],
    ["presentation", { files: true, links: true, minFiles: false, requiredKinds: false }],
  ])("%s", (mode, allowed) => expect(modeAllows(mode as never)).toEqual(allowed));
});

describe("cleanForMode", () => {
  const loaded = row({ min_files: 2, max_files: 5, accepted_families: ["image"], max_bytes_per_file: 10, max_links: 3, required_link_kinds: ["repo"], video_hosts: ["youtube"] });
  it("keeps everything for files and links", () => expect(cleanForMode({ ...loaded, content_mode: "files_and_links" })).toMatchObject({ min_files: 2, max_files: 5, max_links: 3, required_link_kinds: ["repo"], video_hosts: ["youtube"] }));
  it("drops link rules for files only", () => expect(cleanForMode({ ...loaded, content_mode: "files_only" })).toMatchObject({ min_files: 2, max_files: 5, max_links: null, required_link_kinds: [], video_hosts: [] }));
  it("drops file rules for links only", () => expect(cleanForMode({ ...loaded, content_mode: "links_only" })).toMatchObject({ min_files: 0, max_files: null, accepted_families: [], max_bytes_per_file: null, max_links: 3, required_link_kinds: ["repo"] }));
  it("drops the minimum and required kinds for a presentation, keeping caps", () => expect(cleanForMode({ ...loaded, content_mode: "presentation" })).toMatchObject({ min_files: 0, required_link_kinds: [], max_files: 5, max_links: 3 }));
});

describe("saveBody", () => {
  it("sends the fingerprint and preset, includes ids only for saved rows and strips unknown fields", () => {
    const body = saveBody([row({ id: 5, name: "A", key: "zzz" }), row({ name: "B" })], "fp", "hackathon");
    expect(body).toMatchObject({ expected_fingerprint: "fp", preset: "hackathon" });
    expect(body.stages[0]).toMatchObject({ id: 5, name: "A" });
    expect(body.stages[1]).not.toHaveProperty("id");
    expect(body.stages[0]).not.toHaveProperty("key");
  });
  it("never lets the first stage require a previous one, nor the last shortlist or publish", () => {
    const body = saveBody([row({ requires_previous: true, shortlist_after: true, public_after_publish: true }), row({ requires_previous: true, shortlist_after: true, public_after_publish: true })], "fp", "p");
    expect(body.stages.map(s => [s.requires_previous, s.shortlist_after, s.public_after_publish])).toEqual([[false, true, true], [true, false, false]]);
  });
  it("coerces a missing public flag to false and cleans each row for its mode", () => {
    const body = saveBody([row({ content_mode: "links_only", max_files: 4, public_after_publish: undefined }), row()], "fp", "p");
    expect(body.stages[0]).toMatchObject({ public_after_publish: false, max_files: null });
  });
  it("a single stage is both first and last", () => expect(saveBody([row({ requires_previous: true, shortlist_after: true })], "fp", "p").stages[0]).toMatchObject({ requires_previous: false, shortlist_after: false }));
});

describe("stageErrorMessage", () => {
  it("passes through a plain Error's message and is empty for other values", () => {
    expect(stageErrorMessage(new Error("x"))).toBe("x");
    expect(stageErrorMessage("x")).toBe("");
  });
  it("explains an invalid stage by reason, naming the stage when known", () => {
    expect(stageErrorMessage(err("invalid_stage", { reason: "deadline_required", stage: 2 }))).toBe("Stage 2: every stage except the last needs a deadline.");
    expect(stageErrorMessage(err("invalid_stage", { reason: "unknown_preset" }))).toBe("The stage plan was refused: the preset is not recognised.");
    expect(stageErrorMessage(err("invalid_stage", { reason: "links_rule_in_files_only" }))).toBe("The stage plan was refused: a files-only stage cannot have link rules.");
    expect(stageErrorMessage(err("invalid_stage", { reason: "brand_new" }))).toBe("The stage plan was refused: one of its rules is not allowed.");
  });
  it.each([
    ["stage_in_use", {}, "A stage that has submissions, a shortlist, an extension or a judging round cannot be removed. Edit it instead."],
    ["stale_version", {}, "Someone else changed the stages. Reload to see the latest plan, then make your changes again."],
    ["invalid_stage_count", { limit: 12 }, "An event needs between 1 and 12 stages."],
    ["invalid_stage_count", {}, "An event needs between 1 and 50 stages."],
    ["hackathon_stages_quota_reached", { limit: 8 }, "This space allows at most 8 stages on one event. Ask the platform operator to raise it."],
    ["next_stage_open", {}, "The next stage is already open, so the list can no longer change."],
    ["not_a_withdrawn_shortlisted_team", {}, "That team has not withdrawn, or is not on the list."],
    ["no_ranked_source", {}, "This list was hand-picked, so there is no ranked next team."],
    ["no_next_team", {}, "There is no next ranked team left."],
    ["submission_window_by_stage", {}, "This event has several submission stages. Edit each stage's window in the stage editor."],
  ])("%s reads in plain words", (code, body, text) => expect(stageErrorMessage(err(code, body))).toBe(text));
  it("falls back to the error's own message for an unknown code", () => { const e = err("mystery", { detail: "Server said" }); expect(stageErrorMessage(e)).toBe(e.message); });
});

describe("datetime-local conversion", () => {
  it("reads an instant as UTC minutes, and blank as empty", () => { expect(toInput("2026-05-01T10:30:45Z")).toBe("2026-05-01T10:30"); expect(toInput(null)).toBe(""); });
  it("writes the input back as a UTC instant, and blank as null", () => { expect(fromInput("2026-05-01T10:30")).toBe("2026-05-01T10:30:00.000Z"); expect(fromInput("")).toBeNull(); });
});
