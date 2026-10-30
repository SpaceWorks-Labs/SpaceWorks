import { staffRequest } from "../../lib/api";
import type { BackupArchive } from "./backupApi";

/** One makerspace rolled back to a restore point (owner decisions #110d, #111 Q5/Q15/Q16). */
export type SpaceRestoreStage = "requested" | "staging" | "preview_ready" | "applying" | "completed" | "failed" | "aborted";
export type FlaggedMoney = { model: string; pk: string; created_at: string; amount: string; currency: string; status: string };
export type SpaceRestorePreview = {
  snapshot_at: string | null;
  models: Array<{ label: string; live: number; archived: number; removed: number; added: number }>;
  totals: { archived_rows: number; live_rows: number; removed_rows: number; added_rows: number };
  memberships: { removed: number; restored: number };
  accounts: { referenced: number; reattributed: number; erased_since: number };
  money_after_restore_point: FlaggedMoney[];
  evidence_after_restore_point: number;
  objects: { count: number; bytes: number };
  inbound_relinked: number;
  blocking: Array<{ model: string; pk: string; field: string; references: string; reason: string }>;
  blocking_count: number;
  blocked: boolean;
};
export type SpaceRestore = {
  id: string;
  makerspace: number;
  makerspace_slug: string;
  makerspace_name: string;
  archive: string | null;
  source: "space_archive" | "deployment_archive";
  safety_archive: string | null;
  stage: SpaceRestoreStage;
  snapshot_at: string | null;
  preview: Partial<SpaceRestorePreview>;
  progress: { step?: string; percent?: number };
  report: { objects_restored?: number; objects_verified?: number; money_after_restore_point?: FlaggedMoney[] };
  error_code: string;
  error_detail: string;
  blocked: boolean;
  created_at: string;
  finished_at: string | null;
};
export type BackupSchedule = {
  automatic_backups_enabled: boolean;
  platform_nightly: string;
  spaces_nightly: string;
  spaces_per_tick: number;
  daily_keep_days: number;
  weekly_keep_weeks: number;
  on_demand_keep_days: number;
  server_restore_key_configured: boolean;
  last_platform_success_at: string | null;
  spaces: Array<{ makerspace_id: number; slug: string; name: string; last_nightly_at: string | null; last_backup_at: string | null }>;
};

export const ACTIVE_RESTORE_STAGES: SpaceRestoreStage[] = ["requested", "staging", "preview_ready", "applying"];

export const listSpaceBackups = (makerspaceId: number) =>
  staffRequest<BackupArchive[]>(`/admin/makerspace/${makerspaceId}/backups`);
export const requestSpaceBackup = (makerspaceId: number) =>
  staffRequest<BackupArchive>(`/admin/makerspace/${makerspaceId}/backups`, { method: "POST", body: "{}" });
export const listSpaceRestores = (makerspaceId: number) =>
  staffRequest<SpaceRestore[]>(`/admin/makerspace/${makerspaceId}/restores`);
export const startSpaceRestore = (makerspaceId: number, archive: string) =>
  staffRequest<SpaceRestore>(`/admin/makerspace/${makerspaceId}/restores`, { method: "POST", body: JSON.stringify({ archive }) });
export const getSpaceRestore = (restoreId: string) => staffRequest<SpaceRestore>(`/admin/space-restores/${restoreId}`);
export const confirmSpaceRestore = (restoreId: string, confirmSlug: string) =>
  staffRequest<SpaceRestore>(`/admin/space-restores/${restoreId}/confirm`, { method: "POST", body: JSON.stringify({ confirm_slug: confirmSlug }) });
export const abortSpaceRestore = (restoreId: string) =>
  staffRequest<SpaceRestore>(`/admin/space-restores/${restoreId}/abort`, { method: "POST" });
export const getBackupSchedule = () => staffRequest<BackupSchedule>("/admin/platform/backup-schedule");
