import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clearAccessToken, getAccessToken, memberRequest } from "../../lib/api";
import { browserSessionIdentity } from "../../lib/api/reauthentication";
import { reauthenticationKey } from "../auth/reauthenticationApi";
import { forgetOfflineMemberData } from "./memberCard/offlineCard";

export type DeletionBlocker = { code: string; makerspace_id: number | null; makerspace_slug: string | null; makerspace_member_url?: string | null; organization_url?: string | null; organization_id: number | null; count: number; detail: string };
export type DeletionPreview = { deletable: boolean; restorable: boolean; restore_reason: string; blockers: DeletionBlocker[]; reauth: { required: boolean; methods: string[] } };
export type DeletionResult = { deleted_at: string; purge_after: string };
export const deletionKey = () => ["member", "account", "deletion", browserSessionIdentity(getAccessToken("person"))] as const;
export const deletionPreview = () => memberRequest<DeletionPreview>("/auth/account/deletion");
export const deleteAccount = () => memberRequest<DeletionResult>("/auth/account/deletion", { method: "POST", body: JSON.stringify({ confirm: "DELETE" }) });
export const useDeletionPreview = () => useQuery({ queryKey: deletionKey(), queryFn: deletionPreview, retry: false, staleTime: 0 });

export function useDeleteAccount(onDeleted: (result: DeletionResult) => void) {
  const client = useQueryClient();
  return useMutation({ mutationFn: deleteAccount, onSuccess: async (result) => {
    await client.cancelQueries();
    clearAccessToken("person");
    forgetOfflineMemberData();
    onDeleted(result);
    client.clear();
  }, onError: () => {
    void client.invalidateQueries({ queryKey: deletionKey() });
    void client.invalidateQueries({ queryKey: reauthenticationKey });
  } });
}
