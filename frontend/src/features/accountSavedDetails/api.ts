import { memberRequest, memberRequestBlob } from "../../lib/api";
import type { ExportJob, FieldKey, Prefill, PrefillSelector, ResumeAsset, SavedCommand, SavedDetails, SavedValue, SaveIntent } from "./types";
import { parseDetail, parseExport, parseIntent, parsePrefill, parseResume, parseSavedDetails } from "./parsers";

const base = "/member/saved-details/";
function command<T>(path: string, method: string, body: object, operationId: string) {
  return memberRequest<T>(base + path, { method, body: JSON.stringify(body), headers: { "Idempotency-Key": operationId } });
}
export const ownSavedDetails = () => memberRequest<SavedDetails>(base).then(parseSavedDetails);
export const saveDetail = (key: FieldKey, value: SavedValue, cmd: SavedCommand) => command(`${key}/`, "PUT", { ...cmd, value, save_consent: true }, cmd.operation_id).then(parseDetail);
export const deleteDetail = (key: FieldKey, cmd: SavedCommand) => command(`${key}/`, "DELETE", cmd, cmd.operation_id).then(parseDetail);
export const prefillDetails = (selector: PrefillSelector) => memberRequest<Prefill>(base + "prefill/", { method: "POST", body: JSON.stringify(selector) })
  .then(value => parsePrefill(value, selector.context.subject_kind === "stage_response"));
export const saveIntentStatus = (operationId: string) => memberRequest<SaveIntent>(base + `save-intents/${encodeURIComponent(operationId)}/`).then(parseIntent);
export const createResume = (file: File, operationId: string) => command<ResumeAsset>("resume-assets/", "POST", { filename: file.name, mime: "application/pdf", bytes: file.size }, operationId).then(parseResume);
export const resumeStatus = (id: number) => memberRequest<ResumeAsset>(base + `resume-assets/${id}/`).then(parseResume);
export const completeResume = (asset: ResumeAsset, operationId: string) => command<ResumeAsset>(`resume-assets/${asset.asset_id}/complete/`, "POST", { operation_id: operationId, expected_version: asset.version, generation: asset.generation }, operationId).then(parseResume);
export const deleteResume = (asset: ResumeAsset, operationId: string) => command<ResumeAsset>(`resume-assets/${asset.asset_id}/`, "DELETE", { operation_id: operationId, expected_version: asset.version }, operationId).then(parseResume);
export const downloadResume = (id: number) => memberRequestBlob(base + `resume-assets/${id}/download/`);
export const requestExport = (operationId: string) => command<ExportJob>("export/", "POST", {}, operationId).then(parseExport);
export const exportStatus = (id: string) => memberRequest<ExportJob>(base + `export/${encodeURIComponent(id)}/`).then(parseExport);
export const downloadExport = (id: string) => memberRequestBlob(base + `export/${encodeURIComponent(id)}/download/`);

export async function uploadResume(file: File, asset: ResumeAsset, signal?: AbortSignal) {
  if (!asset.upload) throw new Error("Restart this upload.");
  const target = new URL(asset.upload.url);
  if (!["https:", "http:"].includes(target.protocol) || target.username || target.password) throw new Error("The upload address is unavailable.");
  const data = new FormData();
  Object.entries(asset.upload.fields).forEach(([key, value]) => data.append(key, value));
  data.append("file", file);
  const response = await fetch(target, { method: "POST", body: data, credentials: "omit", signal });
  if (!response.ok) throw new Error("The PDF upload failed. Try again.");
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = filename; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
