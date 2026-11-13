import type { ReportCatalogItem } from "./operationsReportsConfig";
import { REPORT_AREAS, reportArea } from "./reportAreas";

/** The Reports hub reads like the module screens: the server names each report's module group (decision 327).
 *  A catalog without that field (an older server, a test fixture) falls back to the legacy area of the key. */
export type ReportGroup = { key: string; label: string; order: number; reports: ReportCatalogItem[] };
export const PINNED_KEY = "pinned";
const LEGACY_ORDER = 100;

export function reportGroupOf(report: ReportCatalogItem): Omit<ReportGroup, "reports"> {
  if (report.group && report.group_label) return { key: report.group, label: report.group_label, order: report.group_order ?? LEGACY_ORDER };
  const area = reportArea(report.key);
  return { key: `area:${area}`, label: area, order: LEGACY_ORDER + REPORT_AREAS.indexOf(area) };
}

export function matchesQuery(report: ReportCatalogItem, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return [report.title, report.key.replace(/-/g, " "), reportGroupOf(report).label].some(text => text.toLowerCase().includes(needle));
}

/** Search and the module-group filter, applied before grouping so counts and headings follow what is shown. */
export function filterReports(reports: ReportCatalogItem[], query: string, group: string): ReportCatalogItem[] {
  return reports.filter(report => matchesQuery(report, query) && (!group || reportGroupOf(report).key === group));
}

export function groupReports(reports: ReportCatalogItem[], pinned: ReadonlySet<string> = new Set(), pinnedLabel = "Pinned"): ReportGroup[] {
  const groups = new Map<string, ReportGroup>();
  const pinnedReports = reports.filter(report => pinned.has(report.key));
  for (const report of reports) {
    if (pinned.has(report.key)) continue;
    const info = reportGroupOf(report);
    const group = groups.get(info.key) ?? { ...info, reports: [] };
    group.reports.push(report);
    groups.set(info.key, group);
  }
  const ordered = [...groups.values()].sort((a, b) => a.order - b.order || a.label.localeCompare(b.label));
  return pinnedReports.length ? [{ key: PINNED_KEY, label: pinnedLabel, order: -1, reports: pinnedReports }, ...ordered] : ordered;
}

/** One chip per group present in the (role- and module-filtered) catalog, in the module-switch order. */
export function groupChoices(reports: ReportCatalogItem[]): { key: string; label: string; count: number }[] {
  return groupReports(reports).map(group => ({ key: group.key, label: group.label, count: group.reports.length }));
}

export type HubEmptyReason = "module_off" | "no_access" | "no_match" | null;
/** Why the hub shows nothing: the Reports module is off, the role unlocks no report, or the search matched none. */
export function hubEmptyReason({ reportsEnabled, catalogCount, visibleCount }: {
  reportsEnabled: boolean; catalogCount: number; visibleCount: number;
}): HubEmptyReason {
  if (!reportsEnabled) return "module_off";
  if (catalogCount === 0) return "no_access";
  return visibleCount === 0 ? "no_match" : null;
}
