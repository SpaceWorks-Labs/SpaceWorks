import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { post } from "./parityRequest";

/** No email, phone or name by design: the lookup is by exact user name and the answer is masked. */
export type PlatformAccount = {
  id: number; username: string; account_kind: string; is_active: boolean;
  access_status: "active" | "restricted" | "suspended"; mfa_enabled: boolean; staff_role_count: number;
};
export type AccountAction = "disable" | "enable" | "reset-two-step";

const BASE = "/admin/platform/accounts";
const key = ["platform-accounts"] as const;

export function useAccountLookup(username: string) {
  return useQuery({
    queryKey: [...key, username],
    queryFn: () => staffRequest<PlatformAccount[]>(`${BASE}?${new URLSearchParams({ username })}`, {}, "platform"),
    enabled: Boolean(username),
  });
}

export function useAccountAction(id: number, action: AccountAction) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) => post<unknown>(`${BASE}/${id}/${action}`, action === "enable" ? {} : { reason }),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}
