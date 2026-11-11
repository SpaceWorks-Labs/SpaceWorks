import { t } from "@lingui/core/macro";

// Decision 248 (C1b): the area reports and exports added this release, findable from the command palette.
// Mirrors operations/report_definitions_completeness.py (required action plus alternates); the server
// still filters the catalogue per definition and module, and the Reports page falls back when one is off.
const REPORTS = (): { key: string; label: string; actions: string[] }[] => [
  { key: "inventory-valuation", label: t`Inventory valuation`, actions: ["edit_inventory"] },
  { key: "inventory-utilisation-by-category", label: t`Inventory use by category`, actions: ["view_inventory"] },
  { key: "overdue-by-borrower", label: t`Overdue items by borrower`, actions: ["view_inventory"] },
  { key: "incidents-register", label: t`Incidents register`, actions: ["manage_makerspace", "manage_machines", "edit_inventory",
    "manage_events", "manage_bookings", "work_repairs", "run_maintenance"] },
  { key: "machine-jobs", label: t`Machine jobs register`, actions: ["manage_machines"] },
  { key: "certification-holders", label: t`Certification holders`, actions: ["manage_machines"] },
  { key: "roster-export", label: t`Member roster`, actions: ["manage_members"] },
  { key: "guest-passes-export", label: t`Guest passes`, actions: ["manage_members"] },
  { key: "volunteer-hours-export", label: t`Volunteer hours`, actions: ["manage_members"] },
  { key: "minors-consent-export", label: t`Minors and guardian consent`, actions: ["manage_members"] },
  { key: "staff-roster-export", label: t`Staff roster`, actions: ["manage_makerspace"] },
];

export function reportCommands(actions: readonly string[], allowedTabs: readonly string[], isSuperadmin: boolean) {
  if (!allowedTabs.includes("reports")) return [];
  return REPORTS().filter(report => isSuperadmin || report.actions.some(action => actions.includes(action)))
    .map(report => ({ key: `report-${report.key}`, label: t`Report: ${report.label}`, tab: "reports", query: { report: report.key } }));
}
