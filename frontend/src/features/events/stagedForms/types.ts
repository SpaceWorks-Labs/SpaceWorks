import type { FormSchemaV2 } from "../../forms/types";
import type { FormSaveIntent } from "../../accountSavedDetails/types";

export type StageScope = { actorId: number; makerspaceId: number; eventId: number };
export type StageAssignment = {
  id: number; stage_form_id: number; title: string; version: number;
  state: "scheduled" | "open" | "completed" | "overdue" | "cancelled";
  due_at: string; opens_at: string; due_revision: number; required: boolean;
  pinned_form_revision_id: number; response_id: number; response_version: number; blocked_actions: string[];
  stage_form_version?: number; allowed_actions?: string[]; next_stage_locked_at?: string | null;
};
export type StageResponse = {
  id: number; version: number; state: "draft" | "submitted" | "locked" | "withdrawn";
  assignment: StageAssignment; selected_revision: number | null; schema: FormSchemaV2;
  answers: { answers: { id: string; value: unknown }[] }; event_date_revision: number;
  current_submitted_revision?: number | null; allowed_actions?: string[];
};
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type CommandResult = { id: number; version: number; state: string; save_intent?: string | null; save_operation_id?: string | null; form_save_intents?: FormSaveIntent[] };
