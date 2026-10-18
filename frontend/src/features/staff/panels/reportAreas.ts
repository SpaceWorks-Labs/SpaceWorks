import type { ReportCatalogItem } from "./operationsReportsConfig";

export const REPORT_AREAS = ["Inventory & loans", "Consumables & stock", "Machines & service", "Bookings", "Events",
  "Membership", "Payments", "Communications & mobile", "Devices/presence/audit"] as const;
export function reportArea(key: string): typeof REPORT_AREAS[number] {
  if (/^booking/.test(key)) return "Bookings";
  if (/^event/.test(key)) return "Events";
  if (/payment|revenue-over|cash-book|accounting|finance|income/.test(key)) return "Payments";
  if (/member|community/.test(key)) return "Membership";
  if (/communications|mobile/.test(key)) return "Communications & mobile";
  if (/device|presence|audit|module-operational/.test(key)) return "Devices/presence/audit";
  if (/consumable|stock|procurement|watch-demand/.test(key)) return "Consumables & stock";
  if (/machine|printer|maintenance|warranty|certification|fablab|service/.test(key)) return "Machines & service";
  return "Inventory & loans";
}
export function reportAreaGroups(reports: ReportCatalogItem[]) {
  return REPORT_AREAS.map(area => [area, reports.filter(report => reportArea(report.key) === area)] as const)
    .filter(([, entries]) => entries.length > 0);
}
