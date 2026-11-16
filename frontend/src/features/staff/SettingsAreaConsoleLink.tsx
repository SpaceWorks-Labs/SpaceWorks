import { t } from "@lingui/core/macro";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

/** Space-wide settings pages whose area also keeps day-to-day settings on its own console page. */
const AREA_CONSOLES = (): Record<string, { tab: string; text: string; link: string; openDialog: boolean }> => ({
  lending: { tab: "inventory", text: t`Inventory switches, pricing and public stats are on the Inventory page.`, link: t`Open Inventory settings`, openDialog: true },
  events: { tab: "events", text: t`Event switches, pricing and public stats are on the Events page.`, link: t`Open Event settings`, openDialog: true },
  bookings: { tab: "bookings", text: t`Booking switches, pricing and public stats are on the Bookings page.`, link: t`Open Booking settings`, openDialog: true },
  materials: { tab: "machines", text: t`Job, session and material settings for each machine type are on the Machines page.`, link: t`Open Machines`, openDialog: false },
});

/** `?settings=open` opens the area page's settings dialog (useDomainSettingsDialog). */
export function withSettingsOpen(href: string) {
  return `${href}${href.includes("?") ? "&" : "?"}settings=open`;
}

/**
 * Decision 255: an area's settings are split between this page (space-wide rules the Space
 * Manager owns) and the area's own page (switches an area manager may hold). Each side
 * points at the other, so neither half is a dead end.
 */
export function AreaConsoleLink({ section, allowedTabs, tabHref }: {
  section: string; allowedTabs: readonly string[]; tabHref: (tab: string) => string;
}) {
  const area = AREA_CONSOLES()[section];
  if (!area || !allowedTabs.includes(area.tab)) return null;
  const href = area.openDialog ? withSettingsOpen(tabHref(area.tab)) : tabHref(area.tab);
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-line pb-4 pt-2 text-sm text-muted">
    <span>{area.text}</span>
    <Link className="inline-flex min-h-11 items-center gap-1 font-semibold text-accent-ink underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" to={href}>
      {area.link}<ArrowUpRight aria-hidden="true" size={14} /></Link>
  </p>;
}
