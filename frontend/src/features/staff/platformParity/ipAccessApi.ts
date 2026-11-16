import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { post, remove, type Page } from "./parityRequest";

export type IpRule = {
  id: number; cidr: string; action: "allow" | "deny"; note: string; expires_at: string | null; active: boolean;
  created_by: string | null; created_at: string;
};
export type IpRuleBody = { cidr: string; action: IpRule["action"]; note?: string; expires_at?: string | null };
export type IpBlock = { id: number; network: string; blocked_until: string; created_at: string; active: boolean };

const RULES = "/admin/platform/ip-rules";
const BLOCKS = "/admin/platform/ip-blocks";
const rulesKey = ["platform-ip-rules"] as const;
const blocksKey = ["platform-ip-blocks"] as const;

export function useIpRules(page: number) {
  return useQuery({ queryKey: [...rulesKey, page], queryFn: () => staffRequest<Page<IpRule>>(`${RULES}?page=${page}`, {}, "platform") });
}

export function useIpBlocks(page: number) {
  return useQuery({ queryKey: [...blocksKey, page], queryFn: () => staffRequest<Page<IpBlock>>(`${BLOCKS}?page=${page}`, {}, "platform") });
}

export function useCreateIpRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: IpRuleBody) => post<IpRule>(RULES, body),
    onSuccess: () => client.invalidateQueries({ queryKey: rulesKey }),
  });
}

export function useDeleteIpRule() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => remove(`${RULES}/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: rulesKey }),
  });
}

export function useUnblock() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => post<{ unblocked: number }>(`${BLOCKS}/${id}/unblock`),
    onSuccess: () => client.invalidateQueries({ queryKey: blocksKey }),
  });
}
