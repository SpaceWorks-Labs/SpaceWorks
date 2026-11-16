import type { PublicStatsDecision, PublicStatsSettings, PublicStatsSettingsPatch, PublicStatsSettingsResponse } from "./api";

const PAGE_FIELDS = ["enabled", "sections", "period", "headline", "tv_mode_enabled", "tv_refresh_seconds"] as const;

export function statsDecision(response: PublicStatsSettingsResponse, group: "settings" | "visibility", key: string): PublicStatsDecision {
  return response.capabilities?.[group]?.[key] ?? { editable: response.can_edit, locked: false };
}

// The server's effective decision includes manager overrides of delegated locks.
export const statsEditable = (decision: PublicStatsDecision) => decision.editable && decision.available !== false;
export const statsVisible = (settings: PublicStatsSettings, key: string) => settings.visibility?.[key] !== false;

/** Submit changed, authorized fields only; another area's stored choices never ride along. */
export function publicStatsPatch(response: PublicStatsSettingsResponse, draft: PublicStatsSettings, area?: string): PublicStatsSettingsPatch {
  const before = response.settings;
  const result = Object.fromEntries(PAGE_FIELDS.filter(key => !area && statsEditable(statsDecision(response, "settings", key))
    && JSON.stringify(before[key]) !== JSON.stringify(draft[key])).map(key => [key, draft[key]])) as PublicStatsSettingsPatch;
  const visibility = Object.fromEntries((response.choices.widgets ?? []).filter(widget =>
    (!area || widget.owner_module === area) && statsEditable(statsDecision(response, "visibility", widget.key))
    && statsVisible(before, widget.key) !== statsVisible(draft, widget.key))
    .map(widget => [widget.key, statsVisible(draft, widget.key)]));
  if (Object.keys(visibility).length) result.visibility = visibility;
  return result;
}
