import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { patch, post } from "./parityRequest";

export type ProviderKey = "sms" | "push" | "whatsapp" | "attestation" | "login_methods";
export type Stamp = { at: string | null; by: string | null };
export type SecretState = { name: string; set: boolean; last_changed: Stamp };
export type ProviderSettings = {
  provider: ProviderKey;
  values: Record<string, string | boolean>;
  secrets: SecretState[];
  info: Record<string, string>;
  updated_at: string | null;
  last_changed: Stamp;
  test: "send" | "check" | null;
};
export type ProviderCheck = { outcome: string; checked?: string[] };

const path = (provider: ProviderKey) => provider === "login_methods" ? "/admin/platform/login-methods" : `/admin/platform/${provider}-settings`;
const key = (provider: ProviderKey) => ["platform-provider-settings", provider] as const;

export function useProviderSettings(provider: ProviderKey) {
  return useQuery({ queryKey: key(provider), queryFn: () => staffRequest<ProviderSettings>(path(provider), {}, "platform") });
}

/** Secrets travel only in this body: blank keeps the stored one, `clear_<name>` removes it. */
export function useSaveProvider(provider: ProviderKey) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, string | boolean>) => patch<ProviderSettings>(path(provider), body),
    onSuccess: data => client.setQueryData(key(provider), data),
  });
}

export function useTestProvider(provider: ProviderKey) {
  return useMutation({ mutationFn: (body: { to?: string }) => post<ProviderCheck>(`${path(provider)}/test`, body) });
}
