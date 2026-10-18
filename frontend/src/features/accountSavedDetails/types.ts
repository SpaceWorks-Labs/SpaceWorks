import type { SavedVaultSavedField, SavedVaultDetailsResponse, SavedVaultExportResponse, SavedVaultIntentResponse,
  SavedVaultPrefillSelector, SavedVaultPrefillInput, Command as WireCommand } from '../../generated/api';
export type FieldKey = "name" | "phone" | "institution" | "organization" | "study_level" | "country" | "skills" | "github_url" | "linkedin_url" | "portfolio_url" | "resume" | "shirt_size" | "dietary_needs" | "accessibility_needs" | "emergency_contact" | "date_of_birth";
export type SavedValue = string | string[] | { name: string; relationship: string; phone: string } | { asset_id: number; sha256: string };
export type SavedField = Omit<SavedVaultSavedField, 'field_key' | 'value'> & { field_key: FieldKey; value: SavedValue | null };
export type SavedDetails = Omit<SavedVaultDetailsResponse, 'fields'> & { fields: SavedField[] };
export type SavedCommand = WireCommand;
export type ResumeAsset = { asset_id: number; state: "uploading" | "validating" | "ready" | "failed" | "deleting" | "deleted"; sha256: string; bytes: number; version: number; generation: number; code?: string;
  upload?: { method: "POST"; url: string; fields: Record<string, string>; expires_at: string } };
export type ExportJob = SavedVaultExportResponse;
export type PrefillSelector = Omit<SavedVaultPrefillInput, 'context'> & { context: SavedVaultPrefillSelector };
export type Prefill = { form_revision: number; event_date_revision: number; values: Record<string, SavedValue>; saved_detail_versions: Partial<Record<FieldKey, number>>; save_defaults: Partial<Record<FieldKey, boolean>>;
  derivation_inputs: Record<string, { source: { kind: "saved_detail"; field_key: "date_of_birth"; version: number }; value: number; as_of_date: string }> };
export type SaveIntent = SavedVaultIntentResponse;
export const savedDetailsKey = (actorId: number) => ["member", "saved-details", window.location.host, actorId] as const;
