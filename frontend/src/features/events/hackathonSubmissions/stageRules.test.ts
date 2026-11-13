import { describe, expect, it } from "vitest";
import { apiError } from "../../../lib/api/errors";
import { checklist, parts, submissionErrorMessage, type ParticipantStage } from "./stageRules";
import type { Project } from "./types";

const stage = (rules: Partial<ParticipantStage["rules"]> = {}, extra: Partial<ParticipantStage> = {}): ParticipantStage => ({
  id: 7, position: 1, name: "Prototype", description: "", opens_at: null, deadline: "2026-12-01T10:00:00Z", grace_minutes: 0,
  effective_deadline: "2026-12-01T10:00:00Z", extended: false, status: "open",
  rules: { content_mode: "files_and_links", required_link_kinds: [], min_files: 0, max_files: null, max_links: null,
    accepted_families: [], max_bytes_per_file: null, video_hosts: [], resubmission: "until_deadline", late_policy: "reject", ...rules },
  custom_fields: [], requires_previous: false, shortlist_after: false, shortlist_label: "", submitted: false, snapshot_id: null,
  submitted_at: null, blocked: null, shortlist_status: null, ...extra });

const project = (patch: Partial<Project> = {}): Project => ({ title: "", tagline: "", problem: "", description: "", challenges: "",
  tech_tags: [], ai_declaration: { used: false, details: "" }, reuse_declaration: { used: false, details: "" }, public_requested: false,
  track_ids: [], prize_ids: [], asset_ids: [], public_asset_ids: [], form_answers: {}, links: [], ...patch });

describe("stage parts and checklist", () => {
  it("hides the files part for links only and the links part for files only", () => {
    expect(parts(stage({ content_mode: "links_only" }))).toMatchObject({ files: false, links: true });
    expect(parts(stage({ content_mode: "files_only" }))).toMatchObject({ files: true, links: false });
    expect(parts(stage({ content_mode: "presentation" }))).toMatchObject({ files: true, links: true, optional: true });
    expect(parts(undefined)).toMatchObject({ files: true, links: true, optional: false });
  });

  it("lists required link kinds, min files and required answers, ticking what the draft meets", () => {
    const s = stage({ required_link_kinds: ["repo", "video"], min_files: 2, max_links: 1 }, {
      custom_fields: [{ key: "problem", label: "Problem statement", type: "long_text", required: true }] });
    const items = checklist(s, project({ asset_ids: [1], links: [{ kind: "repo", url: "https://github.com/a/b", public_requested: false }],
      form_answers: { "stage:7": { problem: "Water" } } }));
    expect(items).toEqual(expect.arrayContaining([
      { label: "At least 2 files", met: false }, { label: "A repo link", met: true }, { label: "A video link", met: false },
      { label: "No more than 1 link", met: true }, { label: "Answer: Problem statement", met: true }]));
  });

  it("flags content the stage does not take", () => {
    const items = checklist(stage({ content_mode: "links_only" }), project({ asset_ids: [4] }));
    expect(items).toContainEqual({ label: "No files (this stage takes links only)", met: false });
    expect(checklist(stage({ content_mode: "presentation" }), project())).toEqual([]);
  });
});

describe("stage error copy", () => {
  const s = stage({}, { custom_fields: [{ key: "problem", label: "Problem statement", type: "long_text", required: true }] });
  it.each([
    [{ code: "submission_link_required", kinds: ["repo"] }, "Add a link of this kind before submitting: repo."],
    [{ code: "submission_files_required", limit: "2" }, "This stage needs at least 2 files."],
    [{ code: "submission_too_many_files", limit: "1" }, "This stage takes at most 1 file. Remove some first."],
    [{ code: "submission_too_many_links", limit: "3" }, "This stage takes at most 3 links. Remove some first."],
    [{ code: "submission_files_disabled" }, "This stage takes links only. Remove the files from this submission."],
    [{ code: "submission_links_disabled" }, "This stage takes files only. Remove the links from this submission."],
    [{ code: "submission_file_type_not_accepted", families: ["deck", "images"] }, "This stage accepts only these file types: deck, images."],
    [{ code: "submission_file_too_large", limit: String(5 * 1024 * 1024) }, "Each file must be at most 5 MB for this stage."],
    [{ code: "submission_video_host_not_allowed", hosts: ["youtube"] }, "Video links must be hosted on: youtube."],
    [{ code: "submission_field_required", fields: ["problem"] }, "Answer these questions first: Problem statement."],
    [{ code: "not_shortlisted" }, "Your team was not shortlisted for this stage."],
    [{ code: "stage_already_submitted" }, "This stage takes one submission only, and your team has already submitted it."],
    [{ code: "entry_fee_required" }, "Pay the entry fee before submitting this stage."],
  ])("explains %o", (body, text) => {
    expect(submissionErrorMessage(apiError(400, body), s)).toBe(text);
  });
});
