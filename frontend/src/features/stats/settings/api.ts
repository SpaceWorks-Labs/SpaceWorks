import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { StatsSectionKey } from "../api";

export type PublicStatsSettings = {
  enabled: boolean;
  sections: StatsSectionKey[];
  period: "month" | "year" | "all" | "fy";
  headline: string[];
  tv_mode_enabled: boolean;
  tv_refresh_seconds: number;
  visibility?: Record<string, boolean>;
};

export type PublicStatsDecision = { editable: boolean; locked: boolean; can_lock?: boolean; code?: string | null;
  via?: string | null; available?: boolean };
export type PublicStatsWidget = { key: string; label: string; section: StatsSectionKey;
  owner_module: string; kind: string };
export type PublicStatsSettingsPatch = Partial<PublicStatsSettings>;

export type PublicStatsSettingsResponse = {
  settings: PublicStatsSettings;
  /** Legacy page-wide authority; individual controls use capabilities when available. */
  can_edit: boolean;
  capabilities?: {
    settings: Record<string, PublicStatsDecision>;
    visibility: Record<string, PublicStatsDecision>;
  };
  choices: {
    sections: { key: StatsSectionKey; label: string }[];
    periods: { key: PublicStatsSettings["period"]; label: string }[];
    metrics: { key: string; section: StatsSectionKey; label: string }[];
    widgets?: PublicStatsWidget[];
    max_headline: number;
    tv_refresh_min: number;
    tv_refresh_max: number;
  };
};

export const publicStatsSettingsKey = (makerspaceId: number) => ["public-stats-settings", makerspaceId] as const;
const path = (makerspaceId: number) => `/admin/makerspace/${makerspaceId}/public-stats-settings`;

export function usePublicStatsSettings(makerspaceId: number) {
  return useQuery({
    queryKey: publicStatsSettingsKey(makerspaceId),
    queryFn: () => staffRequest<PublicStatsSettingsResponse>(path(makerspaceId)),
    retry: false,
  });
}

/** Saving refreshes this panel, the makerspace settings (the page switch) and the public page. */
export function useSavePublicStatsSettings(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PublicStatsSettingsPatch) =>
      staffRequest<PublicStatsSettingsResponse>(path(makerspaceId), { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: data => {
      client.setQueryData(publicStatsSettingsKey(makerspaceId), data);
      for (const key of [["makerspace-settings", makerspaceId], ["makerspaces"], ["staff", "makerspaces"], ["public-stats"],
        ["tenant-bootstrap"]]) void client.invalidateQueries({ queryKey: key });
    },
  });
}
