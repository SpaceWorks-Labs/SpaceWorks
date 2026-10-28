import { staffRequest } from "./requests";

/** Hand-typed until the coordinator regenerates `generated/api.ts`. */
export type SecurityLock = { floor: unknown; note: string; locked_at: string };
export type SecuritySetting = {
  key: string; label: string; description: string; kind: "bool" | "int" | "choice" | "list";
  default: unknown; choices: unknown[]; value: unknown; lock: SecurityLock | null;
};
export type SecuritySettings = {
  makerspace_id: number; settings: SecuritySetting[]; can_edit: boolean; can_lock: boolean;
  edited_as: "space" | "platform" | null;
};

const base = (space: number) => `/admin/makerspaces/${space}/security-settings`;
export const securitySettingsKey = (space: number) => ["security-settings", space] as const;

export const getSecuritySettings = (space: number) => staffRequest<SecuritySettings>(base(space));
export const updateSecuritySettings = (space: number, values: Record<string, unknown>) =>
  staffRequest<SecuritySettings>(base(space), { method: "PATCH", body: JSON.stringify({ values }) });
export const lockSecuritySetting = (space: number, key: string, floor: unknown, note: string) =>
  staffRequest<SecuritySettings>(`${base(space)}/${encodeURIComponent(key)}/lock`,
    { method: "PUT", body: JSON.stringify({ floor, note }) });
export const unlockSecuritySetting = (space: number, key: string) =>
  staffRequest<SecuritySettings>(`${base(space)}/${encodeURIComponent(key)}/lock`, { method: "DELETE" });
