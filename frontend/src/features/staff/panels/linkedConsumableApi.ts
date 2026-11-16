import { t } from "@lingui/core/macro";
import { staffRequest } from "../../../lib/api";

export type UseSource = { kind: "allocation" | "plan"; id: number; planned_quantity: number; used_quantity: number };
export type UseSourcePage = { count: number; next: string | null; previous: string | null; results: UseSource[] };
export type LinkedUseBody = { operation_id: string; quantity: number; note: string; allocation_id: number | null; plan_id: number | null };

export const fetchLinkedUseSources = (tenant: number, product: number, page: number) => staffRequest<UseSourcePage>(`/admin/makerspace/${tenant}/consumables/${product}/equipment-sources?page=${page}`);
export async function submitLinkedUse(tenant: number, product: number, body: Readonly<LinkedUseBody>) {
  const value = await staffRequest<{ status?: unknown; replayed?: unknown }>(`/admin/makerspace/${tenant}/consumables/${product}/use`, { method: "POST", body: JSON.stringify(body) });
  if (!value || value.status !== "recorded" || typeof value.replayed !== "boolean") throw new Error(t`Invalid use response.`);
  return value;
}
