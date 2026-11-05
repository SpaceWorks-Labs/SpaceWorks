import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { patch, post, type Page } from "./parityRequest";

export type OidcProvider = {
  id: number; slug: string; display_name: string; issuer: string; jwks_url: string; client_id: string;
  is_enabled: boolean; allow_auto_link: boolean; created_at: string; updated_at: string;
};
export type OidcProviderBody = Omit<OidcProvider, "id" | "created_at" | "updated_at">;

const BASE = "/admin/platform/oidc-providers";
const key = ["platform-oidc-providers"] as const;

export function useOidcProviders(page: number) {
  return useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Page<OidcProvider>>(`${BASE}?page=${page}`, {}, "platform") });
}

export function useCreateOidcProvider() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: OidcProviderBody) => post<OidcProvider>(BASE, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}

/** Partial change; there is no delete, because linked sign-ins name the provider. */
export function useUpdateOidcProvider(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<OidcProviderBody>) => patch<OidcProvider>(`${BASE}/${id}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}
