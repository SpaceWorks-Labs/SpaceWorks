import { staffRequest } from "./requests";

/** Hand-typed until the coordinator regenerates `generated/api.ts`. */
export type PiiAccessGrant = {
  id: string; scope: "space" | "person"; reason: string; opened_by: string; opened_at: string;
  expires_at: string; closed_at: string | null; close_reason: string; is_own: boolean;
};
export type PiiAccessStatus = {
  makerspace_id: number; viewer_is_superadmin: boolean; pii_visible: boolean;
  active: PiiAccessGrant | null; space_grants: PiiAccessGrant[]; recent: PiiAccessGrant[];
};

const base = (space: number) => `/admin/makerspaces/${space}/pii-access`;
export const piiAccessKey = (space: number) => ["pii-access", space] as const;

export const getPiiAccess = (space: number) => staffRequest<PiiAccessStatus>(base(space));
export const openPiiAccess = (space: number, reason: string) =>
  staffRequest<PiiAccessStatus>(base(space), { method: "POST", body: JSON.stringify({ reason }) });
export const closePiiAccess = (space: number) => staffRequest<PiiAccessStatus>(base(space), { method: "DELETE" });
