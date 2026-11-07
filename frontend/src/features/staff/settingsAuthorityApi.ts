import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";

/** Mirrors `apps/makerspaces/settings_authority_registry.py::MODULE_MANAGER_ACTIONS`. */
export const AUTHORITY_MODULES = ["events", "bookings", "machines", "inventory"] as const;
export type AuthorityModule = typeof AUTHORITY_MODULES[number];

export const MODULE_MANAGER_LABELS: Record<AuthorityModule, string> = {
  events: t`Event settings · Event Managers`,
  bookings: t`Booking settings · Booking Managers`,
  machines: t`Machine settings · Machine Managers`,
  inventory: t`Lending settings · Inventory Managers`,
};

export type SettingsGrant = { id: number; module: AuthorityModule; grantee: number | null; grantee_name: string;
  grantee_email: string; granted_at: string; pii_masked?: boolean };
export type GrantCandidate = { id: number; name: string; email: string };
export type GrantsResponse = { grants: SettingsGrant[]; candidates: Record<AuthorityModule, GrantCandidate[]> };

export type EffectiveKey = { key: string; editable: boolean; via: string | null; locked: boolean;
  code: "setting_not_delegated" | "setting_locked" | null; lock_note: string };
export type EffectiveResponse = { modules: { module: AuthorityModule; space_manager: boolean;
  grant_id: number | null; keys: EffectiveKey[] }[] };

const base = (makerspaceId: number) => `/admin/makerspace/${makerspaceId}/settings-authority`;
export const grantsKey = (makerspaceId: number) => ["settings-authority", makerspaceId, "grants"] as const;
export const effectiveKey = (makerspaceId: number) => ["settings-authority", makerspaceId, "effective"] as const;

export function useSettingsGrants(makerspaceId: number) {
  return useQuery({ queryKey: grantsKey(makerspaceId),
    queryFn: () => staffRequest<GrantsResponse>(`${base(makerspaceId)}/grants`) });
}

export function useUpdateGrants(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { module: AuthorityModule; grantee_ids: number[] }) =>
      staffRequest<GrantsResponse>(`${base(makerspaceId)}/grants`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: async (data) => {
      // The response is the new server state; the per-key answers depend on it too.
      client.setQueryData(grantsKey(makerspaceId), data);
      await client.invalidateQueries({ queryKey: ["settings-authority", makerspaceId] });
      await client.invalidateQueries({ queryKey: ["domain-settings", makerspaceId] });
    },
  });
}

export function useSetLock(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { setting_key: string; locked: boolean; note?: string }) =>
      staffRequest(`${base(makerspaceId)}/locks`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["settings-authority", makerspaceId] });
      await client.invalidateQueries({ queryKey: ["domain-settings", makerspaceId] });
    },
  });
}

export function useEffectiveAuthority(makerspaceId: number, enabled = true) {
  return useQuery({ queryKey: effectiveKey(makerspaceId), enabled,
    queryFn: () => staffRequest<EffectiveResponse>(`${base(makerspaceId)}/effective`) });
}
