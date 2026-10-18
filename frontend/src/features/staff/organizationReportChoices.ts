/** STRATEGIES minus identity-bearing and explicitly excluded organization projections.
 * There is no organization catalog route; never offer member rankings here.
 */
export const organizationReportChoices = [
  "summary", "taken-items", "damaged-missing", "damaged-lost", "recently-added", "most-lent",
  "asset-usage", "loan-throughput", "inventory-utilisation", "stock-health", "request-funnel",
  "problem-reports", "inventory-watch-demand", "qr-scans", "inventory-control", "consumable-usage",
  "consumable-pools", "procurement-performance", "stock-transfers", "stocktake-variance",
  "machine-usage", "machine-downtime", "maintenance-activity", "machine-service", "printer-jobs",
  "machine-errors", "warranty-expiry", "booking-utilization", "event-attendance", "event-signups",
  "event-revenue", "event-funnel", "event-feedback-scores", "membership-growth", "member-retention",
  "membership-revenue", "member-activity", "revenue-over-time", "payments-ageing", "cash-book",
  "payment-reconciliation", "payment-cash-book", "fablab-health", "evidence-compliance", "communications-health", "mobile-devices",
  "mobile-auth", "device-health", "presence-activity", "audit-activity", "organization-membership",
];
export const organizationReportTitle = (key: string) => key.replace(/-/g, " ").replace(/^./, letter => letter.toUpperCase());
// The serializer has no chart_hint. These are the registry's non-line projections.
export const organizationChartHint = (key: string) => key === "member-retention" || key === "qr-scans" ? "heatmap"
  : key === "request-funnel" || key === "event-funnel" || key === "organization-membership" ? "funnel"
    : ["machine-downtime", "stock-transfers", "machine-errors", "printer-jobs", "device-health"].includes(key) ? "stacked_bar" : undefined;

const noGrain = new Set(["summary", "taken-items", "damaged-missing", "damaged-lost", "recently-added", "asset-usage",
  "inventory-watch-demand", "consumable-pools", "warranty-expiry", "event-attendance", "member-retention",
  "member-activity", "payments-ageing", "payment-reconciliation", "payment-cash-book", "fablab-health"]);
export function organizationReportGrains(key: string) {
  return noGrain.has(key) ? [] : key === "evidence-compliance" ? ["day", "month"] : ["day", "week", "month"];
}
