import { describe, expect, it } from "vitest";
import { apiError } from "../../../lib/api/errors";
import { BLANK_RULES, blankStage, cleanForMode, fromPreset, fromSaved, modeAllows, move, saveBody, stageErrorMessage } from "./stageDraft";
import { slug } from "./CustomFieldsEditor";
import type { Preset, SavedStage } from "./types";

const preset: Preset = { key: "idea_final", name: "Idea → Final", description: "", requires_admission: false,
  stages: [{ ...BLANK_RULES, name: "Idea", deadline: "2026-12-01T10:00:00Z" }, { ...BLANK_RULES, name: "Final", requires_previous: true }] };

describe("stage draft helpers", () => {
  it("fills the draft from a preset without ids or dates", () => {
    const rows = fromPreset(preset);
    expect(rows.map(row => [row.name, row.id, row.deadline])).toEqual([["Idea", null, null], ["Final", null, null]]);
    expect(new Set(rows.map(row => row.key)).size).toBe(2);
  });

  it("keeps saved ids and reorders with up and down", () => {
    const saved = [{ ...BLANK_RULES, id: 4, position: 1, version: 1, name: "A" }, { ...BLANK_RULES, id: 5, position: 2, version: 1, name: "B" }] as SavedStage[];
    const rows = fromSaved(saved);
    expect(move(rows, 0, 1).map(row => row.name)).toEqual(["B", "A"]);
    expect(move(rows, 0, -1).map(row => row.name)).toEqual(["A", "B"]);
  });

  it("builds the save body: ids kept, first stage never requires a previous one, last never shortlists", () => {
    const rows = [{ ...blankStage(1), id: 4, requires_previous: true, shortlist_after: true }, { ...blankStage(2), shortlist_after: true }];
    const body = saveBody(rows, "f".repeat(64), "idea_final");
    expect(body.expected_fingerprint).toBe("f".repeat(64));
    expect(body.preset).toBe("idea_final");
    expect(body.stages[0]).toMatchObject({ id: 4, requires_previous: false, shortlist_after: true });
    expect(body.stages[1]).not.toHaveProperty("id");
    expect(body.stages[1]).toMatchObject({ shortlist_after: false, public_after_publish: false });
    expect(body.stages[0]).not.toHaveProperty("key");
  });

  it("drops rules a content mode cannot carry", () => {
    const stage = { ...BLANK_RULES, min_files: 2, max_files: 3, max_links: 4, required_link_kinds: ["repo"], accepted_families: ["deck"] };
    expect(cleanForMode({ ...stage, content_mode: "links_only" })).toMatchObject({ min_files: 0, max_files: null, accepted_families: [], max_links: 4 });
    expect(cleanForMode({ ...stage, content_mode: "files_only" })).toMatchObject({ max_links: null, required_link_kinds: [], min_files: 2 });
    expect(cleanForMode({ ...stage, content_mode: "presentation" })).toMatchObject({ min_files: 0, required_link_kinds: [], max_links: 4 });
    expect(modeAllows("presentation")).toEqual({ files: true, links: true, minFiles: false, requiredKinds: false });
  });

  it("reads typed refusals in plain language", () => {
    expect(stageErrorMessage(apiError(400, { code: "invalid_stage", stage: "2", reason: "deadline_required" })))
      .toBe("Stage 2: every stage except the last needs a deadline.");
    expect(stageErrorMessage(apiError(409, { code: "stage_in_use" }))).toMatch(/cannot be removed/);
    expect(stageErrorMessage(apiError(409, { code: "stale_version" }))).toMatch(/Reload/);
    expect(stageErrorMessage(apiError(400, { code: "invalid_stage_count", limit: "10" }))).toBe("An event needs between 1 and 10 stages.");
  });

  it("makes field keys the server accepts", () => {
    expect(slug("Problem statement!")).toBe("problem_statement");
    expect(slug("2nd idea")).toBe("nd_idea");
  });
});
