import { fields } from "./fieldPresentation";
import type { ExportJob, FieldKey, FormSaveIntent, Prefill, ResumeAsset, SavedDetails, SavedValue, SaveIntent } from "./types";

const keys = new Set([...fields.map(field => field.key), "resume"]);
function requireShape(condition: unknown): asserts condition { if (!condition) throw new Error("Saved details could not be read. Try again."); }
function record(value: unknown): Record<string, unknown> { requireShape(value && typeof value === "object" && !Array.isArray(value)); return value as Record<string, unknown>; }
const integer = (value: unknown, minimum = 0) => typeof value === "number" && Number.isSafeInteger(value) && value >= minimum;
const uuid = (value: unknown) => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

export function parseSavedDetails(value: unknown): SavedDetails {
  const data = record(value);
  requireShape(integer(data.version) && Array.isArray(data.fields) && ["ready", "unavailable"].includes(String(data.readiness)));
  const seen = new Set<string>();
  for (const raw of data.fields) {
    const item = record(raw); const key = String(item.field_key);
    requireShape(keys.has(key) && !seen.has(key) && integer(item.version, 1) && typeof item.sensitive === "boolean" && typeof item.default_save === "boolean");
    seen.add(key);
    if (item.value === null) continue;
    if (key === "resume") {
      const resume = record(item.value); requireShape(integer(resume.asset_id, 1) && /^[a-f0-9]{64}$/.test(String(resume.sha256)));
    } else if (key === "emergency_contact") {
      const contact = record(item.value); requireShape(["name", "relationship", "phone"].every(k => typeof contact[k] === "string"));
    } else if (key === "skills") requireShape(Array.isArray(item.value) && item.value.every(v => typeof v === "string"));
    else requireShape(typeof item.value === "string");
  }
  return data as unknown as SavedDetails;
}

export function parsePrefill(value: unknown, stage = false): Prefill {
  const data = record(value);
  requireShape(integer(data.form_revision, 1) && integer(data.event_date_revision, 1));
  for (const key of Object.keys(record(data.values))) requireShape(keys.has(key));
  for (const [key, version] of Object.entries(record(data.saved_detail_versions))) requireShape(keys.has(key) && integer(version));
  for (const [key, choice] of Object.entries(record(data.save_defaults))) requireShape(keys.has(key) && typeof choice === "boolean");
  for (const raw of Object.values(record(data.derivation_inputs))) {
    const derivation = record(raw); const source = record(derivation.source);
    requireShape(source.kind === "saved_detail" && source.field_key === "date_of_birth" && integer(source.version, 1) && integer(derivation.value) && /^\d{4}-\d{2}-\d{2}$/.test(String(derivation.as_of_date)));
  }
  if (stage) {
    for (const name of ["values", "saved_detail_versions", "save_defaults"])
      requireShape(!("date_of_birth" in record(data[name])) && !("age_at_event" in record(data[name])));
    requireShape(Object.keys(record(data.derivation_inputs)).length === 0);
  }
  return data as unknown as Prefill;
}

export function parseResume(value: unknown): ResumeAsset {
  const data = record(value);
  requireShape(integer(data.asset_id, 1) && ["uploading", "validating", "ready", "failed", "deleting", "deleted"].includes(String(data.state)));
  if (data.state === "ready") requireShape(/^[a-f0-9]{64}$/.test(String(data.sha256)) && integer(data.version, 1) && integer(data.bytes, 1));
  if (data.upload) {
    const upload = record(data.upload);
    requireShape(upload.method === "POST" && typeof upload.url === "string" && typeof upload.expires_at === "string");
    const parameters = record(upload.fields);
    requireShape(Object.values(parameters).every(v => typeof v === "string") && String(parameters.key).startsWith("staging/account/"));
  }
  return data as unknown as ResumeAsset;
}

export function parseExport(value: unknown): ExportJob {
  const data = record(value);
  requireShape(uuid(data.job_id) && ["queued", "building", "ready", "failed", "expired"].includes(String(data.state)));
  return data as unknown as ExportJob;
}

export function parseIntent(value: unknown): SaveIntent {
  const data = record(value);
  requireShape(uuid(data.operation_id) && ["pending", "applied", "conflict", "failed"].includes(String(data.state)) && typeof data.retryable === "boolean");
  parseIntentFields(data.fields);
  return data as unknown as SaveIntent;
}

function parseIntentFields(value: unknown) {
  for (const [key, raw] of Object.entries(record(value))) {
    const item = record(raw); requireShape(keys.has(key) && ["applied", "unchanged", "conflict", "failed"].includes(String(item.state)));
    if (item.version !== undefined) requireShape(integer(item.version, 1));
    if (item.current_version !== undefined) requireShape(integer(item.current_version));
  }
}

/** Parse the canonical response's per-form results before rendering notices. */
export function parseFormSaveIntents(value: unknown): FormSaveIntent[] {
  requireShape(Array.isArray(value));
  const slots = new Set<string>(); const operations = new Set<string>();
  for (const raw of value) {
    const item = record(raw); const slot = String(item.slot);
    requireShape(/^(base|stage:[1-9][0-9]*)$/.test(slot) && !slots.has(slot) && uuid(item.operation_id));
    const operation = String(item.operation_id).toLowerCase();
    requireShape(!operations.has(operation)); slots.add(slot); operations.add(operation);
    parseIntentFields(item.fields);
    if (item.state === "not_requested") requireShape(item.intent_id === null && item.status_url === null && Object.keys(record(item.fields)).length === 0);
    else requireShape(uuid(item.intent_id) && ["pending", "applied", "conflict", "failed"].includes(String(item.state)) &&
      item.status_url === `/api/v1/member/saved-details/save-intents/${item.operation_id}/`);
  }
  return value as FormSaveIntent[];
}

export function parseDetail(value: unknown) {
  const data = record(value);
  requireShape(keys.has(String(data.field_key)) && integer(data.version, 1));
  return data as unknown as { field_key: FieldKey; version: number; value?: SavedValue | null; deleted?: boolean };
}
