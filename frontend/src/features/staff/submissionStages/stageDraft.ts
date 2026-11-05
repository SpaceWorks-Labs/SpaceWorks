import { StructuredApiError } from "../../../lib/api/errors";
import type { ContentMode, Preset, SavedStage, StageDraft, StageRules } from "./types";

const RULE_KEYS: (keyof StageRules)[] = ["name", "description", "opens_at", "deadline", "grace_minutes", "late_policy",
  "resubmission", "requires_previous", "content_mode", "required_link_kinds", "min_files", "max_files", "max_links",
  "accepted_families", "max_bytes_per_file", "video_hosts", "custom_fields", "shortlist_after", "shortlist_label", "public_after_publish"];

export const BLANK_RULES: StageRules = { name: "", description: "", opens_at: null, deadline: null, grace_minutes: 0,
  late_policy: "reject", resubmission: "until_deadline", requires_previous: false, content_mode: "files_and_links",
  required_link_kinds: [], min_files: 0, max_files: null, max_links: null, accepted_families: [], max_bytes_per_file: null,
  video_hosts: [], custom_fields: [], shortlist_after: false, shortlist_label: "", public_after_publish: false };

let counter = 0;
const localKey = () => `stage-${++counter}`;

export function fromSaved(stages: readonly SavedStage[]): StageDraft[] {
  return stages.map(stage => ({ ...BLANK_RULES, ...pick(stage), id: stage.id, key: localKey() }));
}

/** A preset replaces every row; dates are left for the organiser to set. Existing ids are not reused. */
export function fromPreset(preset: Preset): StageDraft[] {
  return preset.stages.map(stage => ({ ...BLANK_RULES, ...stage, opens_at: null, deadline: null, id: null, key: localKey() }));
}

export function blankStage(position: number): StageDraft {
  return { ...BLANK_RULES, name: `Stage ${position}`, id: null, key: localKey() };
}

export function move(rows: readonly StageDraft[], index: number, by: -1 | 1) {
  const target = index + by;
  if (target < 0 || target >= rows.length) return [...rows];
  const next = [...rows]; [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** Which rule controls make sense for a content mode (the server refuses the others). */
export function modeAllows(mode: ContentMode) {
  return { files: mode !== "links_only", links: mode !== "files_only", minFiles: mode === "files_and_links" || mode === "files_only",
    requiredKinds: mode === "files_and_links" || mode === "links_only" };
}

/** Drop values the chosen mode cannot carry, so a mode switch never causes a refusal. */
export function cleanForMode(stage: StageRules): StageRules {
  const allow = modeAllows(stage.content_mode);
  return { ...stage,
    ...(allow.files ? {} : { min_files: 0, max_files: null, accepted_families: [], max_bytes_per_file: null }),
    ...(allow.links ? {} : { max_links: null, required_link_kinds: [], video_hosts: [] }),
    ...(allow.minFiles ? {} : { min_files: 0 }), ...(allow.requiredKinds ? {} : { required_link_kinds: [] }) };
}

export function saveBody(rows: readonly StageDraft[], fingerprint: string, preset: string) {
  return { expected_fingerprint: fingerprint, preset, stages: rows.map((row, index) => {
    const clean = cleanForMode(row);
    return { ...(row.id ? { id: row.id } : {}), ...pick(clean),
      requires_previous: index === 0 ? false : clean.requires_previous,
      shortlist_after: index === rows.length - 1 ? false : clean.shortlist_after,
      public_after_publish: index === rows.length - 1 ? false : Boolean(clean.public_after_publish) };
  }) };
}

function pick(stage: Partial<StageRules>): Partial<StageRules> {
  return Object.fromEntries(RULE_KEYS.filter(key => key in stage).map(key => [key, stage[key]])) as Partial<StageRules>;
}

const REASONS: Record<string, string> = {
  deadline_before_opening: "the deadline must come after the opening time",
  deadline_after_event: "the deadline must fall before the event ends",
  deadline_required: "every stage except the last needs a deadline",
  deadlines_out_of_order: "each deadline must come after the previous stage's deadline",
  first_stage_has_no_previous: "the first stage cannot require a previous stage",
  last_stage_has_no_shortlist: "the last stage cannot end with a shortlist",
  duplicate_field_key: "two custom fields share the same key",
  unknown_choice: "a link kind, file family or video host is not recognised",
  max_files_below_min: "the most files allowed is below the fewest required",
  links_rule_in_files_only: "a files-only stage cannot have link rules",
  files_rule_in_links_only: "a links-only stage cannot have file rules",
  requirement_in_presentation: "a presentation stage cannot require files or links",
  file_cap_above_hard_cap: "the per-file size is above the hard limit for those file types",
  unknown_preset: "the preset is not recognised",
};

export function stageErrorMessage(error: unknown) {
  if (!(error instanceof StructuredApiError)) return error instanceof Error ? error.message : "";
  const body = error.body;
  if (error.code === "invalid_stage") {
    const reason = REASONS[String(body.reason)] ?? "one of its rules is not allowed";
    return body.stage ? `Stage ${String(body.stage)}: ${reason}.` : `The stage plan was refused: ${reason}.`;
  }
  if (error.code === "stage_in_use") return "A stage that has submissions, a shortlist, an extension or a judging round cannot be removed. Edit it instead.";
  if (error.code === "stale_version") return "Someone else changed the stages. Reload to see the latest plan, then make your changes again.";
  if (error.code === "invalid_stage_count") return `An event needs between 1 and ${String(body.limit ?? 10)} stages.`;
  const promote: Record<string, string> = { next_stage_open: "The next stage is already open, so the list can no longer change.",
    not_a_withdrawn_shortlisted_team: "That team has not withdrawn, or is not on the list.",
    no_ranked_source: "This list was hand-picked, so there is no ranked next team.", no_next_team: "There is no next ranked team left." };
  if (error.code && promote[error.code]) return promote[error.code];
  if (error.code === "submission_window_by_stage") return "This event has several submission stages. Edit each stage's window in the stage editor.";
  return error.message;
}

/** Wire value for a datetime-local input (UTC, matching the other programme editors). */
export function toInput(iso: string | null) {
  return iso ? new Date(iso).toISOString().slice(0, 16) : "";
}

export function fromInput(value: string) {
  return value ? new Date(`${value}:00Z`).toISOString() : null;
}
