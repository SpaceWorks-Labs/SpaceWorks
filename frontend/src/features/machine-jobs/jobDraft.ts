import { intakePayload, type IntakeValues, type TypeIntake } from "../inventory/MachineIntakeForm";
import { entriesPayload, entriesProblem, type EntryValues } from "../machine-consumables/entries";
import type { PublicFilamentPool } from "../printing/publicApi";
import type { JobSubmitBody, JobType } from "./types";

export type JobDraft = {
  title: string; description: string; sourceLink: string; copies: number; neededBy: string;
  ownMaterial: boolean; materialNote: string; material: string; color: string; poolId: string; grams: string; settings: string;
  eventId: string; consumables: EntryValues; intake: IntakeValues; acks: { pickup: boolean; failure: boolean; content: boolean };
};

export const emptyDraft: JobDraft = {
  title: "", description: "", sourceLink: "", copies: 1, neededBy: "", ownMaterial: false, materialNote: "",
  material: "", color: "", poolId: "", grams: "", settings: "", eventId: "", consumables: {}, intake: {}, acks: { pickup: false, failure: false, content: false },
};

const trimmed = (value: string) => value.trim() || undefined;

export function todayIso(now = new Date()) {
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

/** What still blocks the details step, in words; empty when it is complete. */
export function detailsProblem(draft: JobDraft, type: JobType | undefined, intake: TypeIntake | undefined, now = new Date()) {
  if (!draft.title.trim()) return "Give your job a title.";
  if (!Number.isInteger(draft.copies) || draft.copies < 1 || draft.copies > 999) return "Copies must be between 1 and 999.";
  if (draft.neededBy && draft.neededBy < todayIso(now)) return "The needed-by date can't be in the past.";
  if (draft.sourceLink.trim() && !/^https?:\/\/\S+$/i.test(draft.sourceLink.trim())) return "The source link must start with http:// or https://.";
  if (type && !type.is_printer) {
    const missing = (intake?.intake_schema.fields ?? []).find(field => field.required && field.type !== "boolean"
      && (draft.intake[field.key] === undefined || draft.intake[field.key] === ""));
    if (missing) return `Fill in "${missing.label}".`;
  }
  const consumable = entriesProblem(type?.consumables ?? [], draft.consumables);
  if (consumable) return consumable;
  if (type?.is_printer && draft.material && !draft.ownMaterial && !draft.poolId && !draft.color) return "Choose a colour for that material.";
  return "";
}

export function submitBody(type: JobType, draft: JobDraft, fileIds: number[], intake: TypeIntake | undefined,
  pools: PublicFilamentPool[] | undefined): JobSubmitBody {
  const base: JobSubmitBody = {
    queue_id: type.queue_id, title: draft.title.trim(), description: trimmed(draft.description), source_link: trimmed(draft.sourceLink),
    file_ids: fileIds, copies: draft.copies, needed_by: draft.neededBy || undefined, own_material: draft.ownMaterial,
    material_note: draft.ownMaterial ? trimmed(draft.materialNote) : undefined,
    event_id: draft.eventId ? Number(draft.eventId) : undefined,
    ...(type.consumables?.length && entriesPayload(type.consumables, draft.consumables).length ? { consumable_estimates: entriesPayload(type.consumables, draft.consumables) } : {}),
    acknowledgements: { pickup_policy: draft.acks.pickup, failure_policy: draft.acks.failure, own_content: draft.acks.content },
  };
  if (!type.is_printer) return { ...base, capability_payload: intakePayload(intake, draft.intake) };
  const pool = draft.ownMaterial ? undefined : pools?.find(row => String(row.id) === draft.poolId);
  return { ...base, preferred_settings: trimmed(draft.settings), estimated_filament_grams: draft.grams.trim() || null,
    ...(draft.ownMaterial ? {} : { material: pool?.material || trimmed(draft.material), color: pool?.color || trimmed(draft.color),
      consumable_pool_id: pool ? pool.id : null }) };
}
