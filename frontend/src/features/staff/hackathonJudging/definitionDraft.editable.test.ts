import { describe, expect, it } from "vitest";
import { changedFields, editableDefinition } from "./definitionDraft";

const round = (over: Record<string, unknown> = {}) => ({ key: "r1", mode: "weighted_1_5", min_reviews: 2, normalization: "none",
  opens_at: "2026-05-01T10:30:45Z", closes_at: null, minutes_per_view: 5, judging_minutes: 60, criteria: [{ key: "c" }], ...over }) as never;

describe("editableDefinition", () => {
  it("normalises round times to minute precision and defaults visibility", () => {
    const out = editableDefinition(round());
    expect(out.opens_at).toBe("2026-05-01T10:30:00Z");
    expect(out.closes_at).toBeNull();
    expect(out.visibility).toBe("assigned");
    expect(out.fresh_eyes).toBe(false);
    expect(out.panel).toEqual([]);
    expect(out.submission_stage_id).toBeNull();
    expect(out.share_feedback).toBe(false);
    expect(out.judge_reminders).toBe(false);
    expect(out.criteria).toEqual([{ key: "c" }]);
    expect(out).not.toHaveProperty("guidance");
  });
  it("keeps explicit round flags and visibility", () => {
    const out = editableDefinition(round({ visibility: "all", fresh_eyes: 1, panel: [3], submission_stage_id: 7, share_feedback: true, judge_reminders: true }));
    expect(out).toMatchObject({ visibility: "all", fresh_eyes: true, panel: [3], submission_stage_id: 7, share_feedback: true, judge_reminders: true });
  });
  it("adds guidance and a two-decimal exploration for pairwise rounds", () => {
    const out = editableDefinition(round({ mode: "pairwise", guidance: undefined, exploration: undefined }));
    expect(out).toMatchObject({ guidance: "", exploration: "0.10" });
    expect(out).not.toHaveProperty("criteria");
    expect(editableDefinition(round({ mode: "pairwise", guidance: "g", exploration: 0.256 }))).toMatchObject({ guidance: "g", exploration: "0.26" });
  });
  it("describes a prize with its award fields", () => expect(editableDefinition({ name: "P", description: "d", award_count: 2, track_id: 1,
    sponsor_id: null, winner_selection_mode: "manual" } as never)).toEqual({ name: "P", description: "d", award_count: 2, track_id: 1,
    sponsor_id: null, winner_selection_mode: "manual", amount_per_winner: null }));
  it("describes a track with its capacity", () => expect(editableDefinition({ name: "T", description: "d", capacity: 5 } as never)).toEqual({ name: "T", description: "d", capacity: 5 }));
});

describe("changedFields", () => {
  it("returns only the keys whose value changed, comparing deeply", () => expect(changedFields({ a: 1, b: [1, 2], c: "x" }, { a: 1, b: [1, 3], c: "x", d: 4 })).toEqual({ b: [1, 3], d: 4 }));
  it("is empty when nothing changed", () => expect(changedFields({ a: { x: 1 } }, { a: { x: 1 } })).toEqual({}));
});
