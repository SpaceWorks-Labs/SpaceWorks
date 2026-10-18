import { fields } from "./fieldPresentation";
import type { ExportJob, FieldKey, Prefill, ResumeAsset, SavedDetails, SavedValue, SaveIntent } from "./types";

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

export function parsePrefill(value: unknown): Prefill {
  const data = record(value);
  requireShape(integer(data.form_revision, 1) && integer(data.event_date_revision, 1));
  record(data.values);
  for (const [key, version] of Object.entries(record(data.saved_detail_versions))) requireShape(keys.has(key) && integer(version));
  for (const [key, choice] of Object.entries(record(data.save_defaults))) requireShape(keys.has(key) && typeof choice === "boolean");
  for (const raw of Object.values(record(data.derivation_inputs))) {
    const derivation = record(raw); const source = record(derivation.source);
    requireShape(source.kind === "saved_detail" && source.field_key === "date_of_birth" && integer(source.version, 1) && integer(derivation.value) && /^\d{4}-\d{2}-\d{2}$/.test(String(derivation.as_of_date)));
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
  for (const [key, raw] of Object.entries(record(data.fields))) {
    const item = record(raw); requireShape(keys.has(key) && ["applied", "conflict", "failed"].includes(String(item.state)));
    if (item.version !== undefined) requireShape(integer(item.version, 1));
    if (item.current_version !== undefined) requireShape(integer(item.current_version));
  }
  return data as unknown as SaveIntent;
}

export function parseDetail(value: unknown) {
  const data = record(value);
  requireShape(keys.has(String(data.field_key)) && integer(data.version, 1));
  return data as unknown as { field_key: FieldKey; version: number; value?: SavedValue | null; deleted?: boolean };
}
