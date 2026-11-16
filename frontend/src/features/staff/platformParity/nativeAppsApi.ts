import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { patch, post, type Page } from "./parityRequest";

export type NativeApp = {
  id: number; makerspace: number | null; app_id: string; platform: "android" | "apple"; environment: "development" | "production";
  verifier_config_key: string; signing_identities: string[]; min_supported_version: string | null;
  status: "pending" | "approved" | "revoked"; approved_by: string | null; revoked_at: string | null; created_at: string; updated_at: string;
};
export type NativeAppBody = Omit<NativeApp, "id" | "approved_by" | "revoked_at" | "created_at" | "updated_at">;

const BASE = "/admin/platform/native-apps";
const key = ["platform-native-apps"] as const;

export function useNativeApps(page: number) {
  return useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Page<NativeApp>>(`${BASE}?page=${page}`, {}, "platform") });
}

/** Register when `id` is null, otherwise change that row; setting `status: "revoked"` ends its devices' sign-ins. */
export function useSaveNativeApp(id: number | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<NativeAppBody>) => id === null ? post<NativeApp>(BASE, body) : patch<NativeApp>(`${BASE}/${id}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}
