import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { memberRequest, StructuredApiError } from "../../../lib/api";
import { getPasskeyAssertion } from "../../auth/passkeys/webauthn";

/** Account linking: the signed-in person proves a second (former staff) account and folds it in. */
export type MergeMethod = "credentials" | "email_codes";
export type MergeIntent = { intent_id: string; method: MergeMethod; state: string; expires_at: string };
export type MergeProof = { password: string; otp: string } | { survivor_code: string; source_code: string }
  | { password: string; passkey: { ceremony: string; credential: unknown } };
export type MakerspaceRef = { id: number; slug: string; name: string };
export type RoleGrant = { makerspace: MakerspaceRef; roles: string[] };
export type MergePreview = {
  source: { id: number; username: string; display_name: string };
  privilege_diff: { roles_gained: RoleGrant[]; duplicate_staff_rows: RoleGrant[] };
  grace_opens: boolean;
  moves: { repoint: { rows: number }; keep_on_shell: { rows: number }; unique_resolve: { rows: number; kept_on_shell: number } };
  conflicts: { model: string; field: string; kept_on_shell: boolean }[];
  preview_sha256: string;
  expires_at: string;
};
export type MergeResult = {
  merged: true; record_id: string | number; roles_gained: RoleGrant[]; grace_opened: boolean;
  counts: { repointed: number; kept_on_shell: number; unique_moved: number; unique_kept: number; revoked: number };
};

const BASE = "/auth/account-merge";
const post = <T>(path: string, body?: object) =>
  memberRequest<T>(`${BASE}${path}`, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) });
const intentPath = (id: string, action: string) => `/${encodeURIComponent(id)}/${action}`;

export const startMerge = (identifier: string, method: MergeMethod) => post<MergeIntent>("/start", { identifier, method });
export const proveMerge = (id: string, proof: MergeProof) => post<MergeIntent>(intentPath(id, "prove"), proof);
/**
 * #65 (GAP2 M6): the other account's password, then ITS passkey instead of the authenticator code.
 * The password is checked before any passkey is offered; the browser's own sheet is the only prompt.
 */
export async function proveMergeWithPasskey(id: string, password: string) {
  const { ceremony, options } = await post<{ ceremony: string; options: unknown }>(intentPath(id, "passkey-options"), { password });
  const credential = await getPasskeyAssertion(options);
  return proveMerge(id, { password, passkey: { ceremony, credential } });
}
export const resendMergeCodes = (id: string) => post<MergeIntent>(intentPath(id, "resend"));
export const fetchMergePreview = (id: string) => memberRequest<MergePreview>(`${BASE}${intentPath(id, "preview")}`);
export const confirmMerge = (id: string, previewSha256: string) => post<MergeResult>(intentPath(id, "confirm"), { preview_sha256: previewSha256 });
export const cancelMerge = (id: string) => post<MergeIntent>(intentPath(id, "cancel"));

export const mergePreviewKey = (id: string) => ["account-merge", id, "preview"] as const;
export const mergeMeKey = ["member", "account", "me"] as const;

/** `merge_suggested` from the person's auth payload; false until it loads or when it fails. */
export function useMergeSuggested(enabled: boolean) {
  const me = useQuery({ queryKey: mergeMeKey, enabled, retry: false,
    queryFn: async () => (await memberRequest<{ merge_suggested?: boolean } | undefined>("/auth/me")) ?? {} });
  return enabled && me.data?.merge_suggested === true;
}

const COPY: Record<string, string> = {
  merge_not_allowed: t`This account can't be linked.`,
  proof_failed: t`That didn't match. Check and try again.`,
  factor_enrolment_required: t`The other account has no authenticator. Use the emailed codes instead.`,
  proof_expired: t`This link request expired. Start again.`,
  recent_reauth_required: t`Confirm it's you, then try again.`,
  preview_stale: t`Something changed. Review again.`,
  tenant_gated: t`A makerspace is temporarily read-only. Try again later.`,
  already_merged: t`These accounts are already linked.`,
};
export const errorCode = (error: unknown) => error instanceof StructuredApiError ? error.code : undefined;
export const linkErrorCopy = (error: unknown) => COPY[errorCode(error) ?? ""] ?? t`Couldn't complete this step. Try again.`;

/** Role keys arrive as slugs ("space_manager"); show them as words. */
export const roleLabel = (role: string) => /^[a-z_]+$/.test(role)
  ? role.charAt(0).toUpperCase() + role.slice(1).replace(/_/g, " ") : role;
