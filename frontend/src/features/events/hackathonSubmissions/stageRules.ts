import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../../lib/api/errors";
import type { Project } from "./types";

export type StageField = { key: string; label: string; type: "short_text" | "long_text" | "choice" | "url"; required: boolean;
  choices?: string[] | null; help?: string | null };
export type ParticipantStage = {
  id: number; position: number; name: string; description: string; opens_at: string | null; deadline: string; grace_minutes: number;
  effective_deadline: string; extended: boolean; status: "upcoming" | "open" | "late" | "closed";
  rules: { content_mode: "files_and_links" | "files_only" | "links_only" | "presentation"; required_link_kinds: string[];
    min_files: number; max_files: number | null; max_links: number | null; accepted_families: string[];
    max_bytes_per_file: number | null; video_hosts: string[]; resubmission: "until_deadline" | "once"; late_policy: "reject" | "accept_flagged" };
  custom_fields: StageField[]; requires_previous: boolean; shortlist_after: boolean; shortlist_label: string;
  submitted: boolean; snapshot_id: number | null; submitted_at: string | null;
  blocked: "previous_stage_required" | "shortlist_pending" | "not_shortlisted" | null;
  shortlist_status: "pending" | "shortlisted" | "not_shortlisted" | null;
  /** S4: judge feedback the organisers released for this stage, without judge names. */
  feedback?: string[];
};

/** What the form shows for a stage's content mode. */
export function parts(stage: ParticipantStage | undefined) {
  const mode = stage?.rules.content_mode ?? "files_and_links";
  return { files: mode !== "links_only", links: mode !== "files_only", optional: mode === "presentation" };
}

export const answerKey = (stage: ParticipantStage) => `stage:${stage.id}`;

export function stageAnswers(project: Project, stage: ParticipantStage): Record<string, string> {
  const value = project.form_answers[answerKey(stage)];
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, string> : {};
}

export type CheckItem = { label: string; met: boolean };

/** The requirement checklist, computed from the current draft (the server enforces it at submit). */
export function checklist(stage: ParticipantStage, project: Project): CheckItem[] {
  const { rules } = stage; const items: CheckItem[] = []; const files = project.asset_ids.length; const links = project.links.filter(l => l.url.trim());
  const show = parts(stage);
  if (rules.content_mode !== "presentation" && show.files && show.links) items.push({ label: t`At least one file or link`, met: files + links.length > 0 });
  if (rules.content_mode === "files_only") items.push({ label: t`At least one file`, met: files > 0 });
  if (rules.content_mode === "links_only") items.push({ label: t`At least one link`, met: links.length > 0 });
  if (rules.min_files > 0) items.push({ label: t`At least ${rules.min_files} ${rules.min_files === 1 ? "file" : "files"}`, met: files >= rules.min_files });
  if (show.files && rules.max_files !== null) items.push({ label: t`No more than ${rules.max_files} ${rules.max_files === 1 ? "file" : "files"}`, met: files <= rules.max_files });
  if (show.links && rules.max_links !== null) items.push({ label: t`No more than ${rules.max_links} ${rules.max_links === 1 ? "link" : "links"}`, met: links.length <= rules.max_links });
  for (const kind of rules.required_link_kinds) items.push({ label: t`A ${kind} link`, met: links.some(link => link.kind === kind) });
  if (!show.files && files) items.push({ label: t`No files (this stage takes links only)`, met: false });
  if (!show.links && links.length) items.push({ label: t`No links (this stage takes files only)`, met: false });
  const answers = stageAnswers(project, stage);
  for (const field of stage.custom_fields.filter(f => f.required)) items.push({ label: t`Answer: ${field.label}`, met: Boolean(answers[field.key]?.trim()) });
  return items;
}

const MB = 1024 * 1024;
const list = (value: unknown) => (Array.isArray(value) ? value.map(String).join(", ") : "");

/** Plain-language copy for every typed stage error (#177-#180). */
export function submissionErrorMessage(error: unknown, stage?: ParticipantStage) {
  if (!(error instanceof StructuredApiError)) return error instanceof Error ? error.message : "";
  const body = error.body; const limit = Number(body.limit);
  const labels = (keys: unknown) => (Array.isArray(keys) ? keys.map(key => stage?.custom_fields.find(f => f.key === key)?.label ?? String(key)).join(", ") : "");
  const copy: Record<string, string> = {
    submission_link_required: `Add a link of this kind before submitting: ${list(body.kinds)}.`,
    submission_files_required: `This stage needs at least ${limit} ${limit === 1 ? "file" : "files"}.`,
    submission_too_many_files: `This stage takes at most ${limit} ${limit === 1 ? "file" : "files"}. Remove some first.`,
    submission_too_many_links: `This stage takes at most ${limit} ${limit === 1 ? "link" : "links"}. Remove some first.`,
    submission_files_disabled: "This stage takes links only. Remove the files from this submission.",
    submission_links_disabled: "This stage takes files only. Remove the links from this submission.",
    submission_file_type_not_accepted: `This stage accepts only these file types: ${list(body.families)}.`,
    submission_file_too_large: `Each file must be at most ${Math.round(limit / MB)} MB for this stage.`,
    submission_video_host_not_allowed: `Video links must be hosted on: ${list(body.hosts)}.`,
    submission_field_required: `Answer these questions first: ${labels(body.fields)}.`,
    submission_field_invalid: `Check your answers to: ${labels(body.fields)}.`,
    submission_content_required: "Add at least one file or link before submitting.",
    stage_not_open: "This stage has not opened yet.",
    stage_closed: "This stage is closed: the organisers have already chosen who continues.",
    previous_stage_required: "Submit the previous stage first.",
    shortlist_pending: "The shortlist for the previous stage is not published yet.",
    not_shortlisted: "Your team was not shortlisted for this stage.",
    stage_already_submitted: "This stage takes one submission only, and your team has already submitted it.",
    submission_deadline: "The deadline for this stage has passed.",
    entry_fee_required: "Pay the entry fee before submitting this stage.",
    team_payment_required: "The team registration must be paid before submitting.",
  };
  return (error.code && copy[error.code]) || error.message;
}

export const BLOCKED: Record<NonNullable<ParticipantStage["blocked"]>, string> = {
  previous_stage_required: "Submit the previous stage to take part in this one.",
  shortlist_pending: "Opens to shortlisted teams once the shortlist is published.",
  not_shortlisted: "Your team was not shortlisted for this stage. Your earlier submissions stay as you submitted them.",
};
