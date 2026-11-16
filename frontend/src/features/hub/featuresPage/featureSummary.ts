import { t } from "@lingui/core/macro";
import type { ModuleKey } from "../../../lib/retiredModules";
import { featureCatalogue } from "./catalogue";
import { featureAreas, moduleDefault } from "./featureAreas";
import { featuresByModule } from "./moduleFeatures";

export type ModuleSummary = { key: ModuleKey; features: number; reports: number; analytics: number; limits: number; integrations: number };

/** Counts for a module card: every number comes from the same data the module page lists. */
export function moduleSummary(key: ModuleKey): ModuleSummary {
  const entry = featureCatalogue()[key];
  return { key, features: featuresByModule()[key].length, reports: entry.reports.length, analytics: entry.analytics.length,
    limits: entry.limits.length, integrations: entry.integrations.length };
}

/** "12 features · 4 reports": the parts that are zero are left out. */
export function summaryLine(summary: ModuleSummary): string {
  const parts = [
    summary.features ? t`${summary.features} features` : "", summary.reports ? t`${summary.reports} reports` : "",
    summary.limits ? t`${summary.limits} limits` : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : t`Part of the core`;
}

/** The docs page of the area a module belongs to (featureAreas places every module). */
export const moduleDocs = (key: ModuleKey) => featureAreas().find(area => (area.modules as string[]).includes(key))?.docs ?? "/docs/modules";

export function defaultLabel(key: ModuleKey) {
  return { always: t`Always on`, on: t`On in a new setup`, off: t`Off until you turn it on` }[moduleDefault(key)];
}

const FAMILY_LABELS = (): Record<string, string> => ({
  ui: t`Interface`, loans: t`Loans`, inventory: t`Inventory`, charges: t`Charges`, billing: t`Billing`, finance: t`Finance`,
  payments: t`Payments`, maintenance: t`Maintenance`, staff: t`Staff`, safety: t`Safety`, platform: t`Platform`, legal: t`Legal pages`,
  public_site: t`Public site`, calendar: t`Calendar`, packs: t`Space packs`, cards: t`Cards`, display: t`Displays`, presence: t`Presence`,
  notifications: t`Notifications`, membership: t`Membership`, machines: t`Machines`, events: t`Events`, bookings: t`Bookings`,
  shop: t`Shop`, reports: t`Reports`, stocktake: t`Stocktake`, mobile: t`Mobile`, email: t`Email`,
});

export function familyLabel(family: string): string {
  const known = FAMILY_LABELS()[family];
  if (known) return known;
  const words = family.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
