import { t } from "@lingui/core/macro";

// A function, not a module constant: `t` must run after the locale is active.
const areaLabel = (area: string): string => ({
  inventory: t`Inventory`, machines: t`Machines`, events: t`Events`, bookings: t`Bookings`,
  payments: t`Payments`, email: t`Email`, warranty: t`Warranties`,
} as Record<string, string>)[area] ?? t`Other`;

/** Open item A31 (U13): name the areas whose numbers could not load instead of showing a silent 0. */
export function DashboardFailedAreas({ areas, onRetry }: { areas?: string[]; onRetry: () => void }) {
  if (!areas?.length) return null;
  const names = [...new Set(areas.map(areaLabel))].join(", ");
  return <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warn bg-surface p-3 text-sm text-ink">
    <p className="min-w-0">{t`Couldn't load some numbers: ${names}. Counts for these areas may show 0.`}</p>
    <button type="button" className="desk-button" onClick={onRetry}>{t`Try again`}</button>
  </div>;
}
