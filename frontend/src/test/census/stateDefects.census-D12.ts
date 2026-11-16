import type { Phase } from "./fetch.census-D12";
import type { RouteCase } from "./source.census-D12";

// Source-confirmed presentation omissions, not admission/driver exceptions.
// Setup validates mounting and the actual domain response outside it.fails.
export const STATE_DEFECTS = [
  { id: "CENSUS-D12-53", leaf: "BackupRestorePanel", phase: "loading",
    source: "features/staff/panels/DashboardArchiveStatus.tsx:14",
    fix: "Render a labelled status while BackupStatusCard's query is pending; also replace SelfHostMoveCard.tsx:26's pending null with a labelled status." },
  { id: "CENSUS-D12-54", screen: "LegalPage", phase: "empty",
    source: "features/legal/LegalPage.tsx:40",
    fix: "Render translated empty-content copy when a successful legal-page response has empty markdown, instead of an empty article." },
  { id: "CENSUS-D12-56", leaf: "MakerspaceSettingsPanel", phase: "loading",
    source: "features/staff/MakerspaceSettingsPanel.tsx:97",
    fix: "Keep the last-known-value settings form, but expose a labelled pending status while settings.isLoading; disabling controls alone does not announce loading." },
] as const;
export function stateDefect(row: RouteCase, phase: Phase) {
  return STATE_DEFECTS.find(item => item.phase === phase && ("screen" in item ? row.screen === item.screen : row.leaves?.includes(item.leaf)));
}
