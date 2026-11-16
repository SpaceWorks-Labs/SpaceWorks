import type { ShellItem, ShellSection } from "../../components/shell";

// Decision 242 / U12: on a phone the Space Manager and the superadmin get a bottom bar like the handover
// desk and the member portal: their four most-used destinations, then "More" for the full menu.
const SPACE = ["dashboard", "schedule", "requests", "notifications", "bookings", "events", "payments"];
const PLATFORM = ["platform-dashboard", "platform-spaces", "platform-inbox", "platform-analytics"];

/** The bar's items, taken from the already permission- and module-filtered menu (so badges carry over). */
export function staffBottomNav(nav: ShellSection[], mode: "space" | "platform" | null): ShellItem[] | undefined {
  if (!mode) return undefined;
  const items = nav.flatMap(section => [...section.items, ...section.more ?? []]);
  const picked = (mode === "space" ? SPACE : PLATFORM).map(key => items.find(item => item.key === key))
    .filter((item): item is ShellItem => Boolean(item)).slice(0, 4);
  return picked.length >= 2 ? picked : undefined;
}
