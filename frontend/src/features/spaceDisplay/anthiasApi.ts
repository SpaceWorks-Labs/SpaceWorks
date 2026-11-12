import { useQuery } from "@tanstack/react-query";
import { staffRequest, tenantPublicRequest } from "../../lib/api";
import { spaceNowKeys, type AdminDisplay, type DisplayPrivacy } from "./api";

// Hand-typed from the DISPLAY-2 contract (decision 325); `generated/api.ts` is regenerated at staging.
export type AnthiasPlayer = { id: number; name: string; host_url: string; username: string; has_password: boolean;
  api_version: string; anthias_version: string; status: "never" | "ok" | "error"; last_error: string; last_synced_at: string | null };
export type AnthiasPlayerList = { enabled: boolean; allow_private_hosts: boolean; players: AnthiasPlayer[] };
export type AnthiasPlayerInput = Partial<{ name: string; host_url: string; username: string; password: string }>;
export type AnthiasTest = { ok: boolean; reason: string; api_version: string; anthias_version: string };

export type NowSection = "here_now" | "machines" | "events" | "public_stats" | "opening_hours";
export const NOW_SECTIONS: NowSection[] = ["here_now", "machines", "events", "public_stats", "opening_hours"];
export type NowConfig = { sections: NowSection[]; privacy: DisplayPrivacy; refresh_seconds: number };

const base = (id: number) => `/admin/makerspace/${id}`;
export const anthiasKeys = { players: (id: number) => ["presence", "staff", id, "anthias"] as const,
  nowConfig: (id: number) => ["presence", "staff", id, "now-config"] as const };

export const anthiasApi = {
  list: (id: number) => staffRequest<AnthiasPlayerList>(`${base(id)}/anthias-players`),
  create: (id: number, input: AnthiasPlayerInput) =>
    staffRequest<AnthiasPlayer>(`${base(id)}/anthias-players`, { method: "POST", body: JSON.stringify(input) }),
  update: (id: number, playerId: number, input: AnthiasPlayerInput) =>
    staffRequest<AnthiasPlayer>(`${base(id)}/anthias-players/${playerId}`, { method: "PATCH", body: JSON.stringify(input) }),
  remove: (id: number, playerId: number) => staffRequest<void>(`${base(id)}/anthias-players/${playerId}`, { method: "DELETE" }),
  test: (id: number, playerId: number) => staffRequest<AnthiasTest>(`${base(id)}/anthias-players/${playerId}/test`, { method: "POST" }),
  sync: (id: number, playerId: number) => staffRequest<AnthiasPlayer>(`${base(id)}/anthias-players/${playerId}/sync`, { method: "POST" }),
  setPlayers: (id: number, displayId: number, playerIds: number[]) =>
    staffRequest<AdminDisplay>(`${base(id)}/presence-displays/${displayId}/players`, { method: "PUT", body: JSON.stringify({ player_ids: playerIds }) }),
};

export const nowConfigApi = {
  get: (id: number) => staffRequest<NowConfig>(`${base(id)}/presence-now-config`),
  put: (id: number, input: Partial<NowConfig>) => staffRequest<NowConfig>(`${base(id)}/presence-now-config`, { method: "PUT", body: JSON.stringify(input) }),
};

/** The public page's section list, order and privacy; falls back to the built-in default while loading or on error. */
export function usePublicNowConfig(slug: string) {
  return useQuery({ queryKey: spaceNowKeys.config(slug), enabled: Boolean(slug), staleTime: 60_000, retry: 1,
    queryFn: () => tenantPublicRequest<NowConfig>(slug, `/public/makerspaces/${encodeURIComponent(slug)}/presence/now-config/`) });
}
