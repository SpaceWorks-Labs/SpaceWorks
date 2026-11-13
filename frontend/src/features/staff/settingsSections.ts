import { t } from "@lingui/core/macro";

/**
 * The Settings page's information architecture (decision 255): one routed subpage per
 * section under `/admin/settings/<section>`, grouped by how a Space Manager thinks about the
 * space — Space, People, Areas, Money, Communication, Integrations, Administration — the
 * same shape Shopify admin, Stripe and Linear use (a short list of plain-noun groups, each
 * a handful of pages). A group may also list a settings page that lives on its own console
 * tab (`tab:<tab>[/<view>]`, e.g. Staff & roles or the Shop's settings view), so every
 * setting has exactly one home in this menu even when its editor lives elsewhere.
 *
 * Presentation only: which sections exist for this actor and space is decided where the
 * sections are built (permission + module gates), and the server stays the authority.
 */
export type SettingsGroup = { key: string; label: string; items: readonly string[] };

export const settingsGroups = (): readonly SettingsGroup[] => [
  { key: "space", label: t`Space`, items: ["overview", "general", "branding", "public-page", "public-stats"] },
  { key: "people", label: t`People`, items: ["tab:users", "membership", "units", "guest-passes", "community", "presence"] },
  { key: "areas", label: t`Areas`, items: ["tab:modules", "features", "lending", "materials", "events", "bookings", "tab:shop/settings"] },
  { key: "money", label: t`Money`, items: ["money", "pricing", "tab:donations/profile"] },
  { key: "communication", label: t`Communication`, items: ["notifications", "channels", "email", "tab:emailtemplates", "tab:email-logs"] },
  { key: "integrations", label: t`Integrations`, items: ["integrations", "health", "tab:api"] },
  { key: "administration", label: t`Administration`, items: ["privacy", "hosting", "tab:security", "tab:audit", "tab:exports", "tab:backups", "tab:usage", "tab:migration"] },
];

/** A menu entry that opens another console page: `tab:shop/settings` → { tab: "shop", view: "settings" }. */
export function settingsLinkTarget(item: string): { tab: string; view: string } | null {
  if (!item.startsWith("tab:")) return null;
  const [tab, view = ""] = item.slice(4).split("/");
  return { tab, view };
}

/** Old anchors and subpaths whose page was renamed or folded in by a later split. */
const ALIASES: Readonly<Record<string, string>> = { start: "overview", tools: "overview" };

/** Ids in nav order, narrowed to the sections this actor and space actually have. */
export function orderedSettingsSections(available: readonly string[]): string[] {
  return settingsGroups().flatMap(group => group.items.filter(id => available.includes(id)));
}

/** Where `/admin/settings` lands: the first section the actor may open. */
export function settingsLanding(available: readonly string[]): string {
  return orderedSettingsSections(available)[0] ?? "";
}

/** `#integrations` from a pre-split bookmark → the subpage that holds it, if any. */
export function settingsSectionForHash(hash: string, available: readonly string[]): string {
  const id = decodeURIComponent(hash.replace(/^#/, ""));
  const resolved = ALIASES[id] ?? id;
  return available.includes(resolved) ? resolved : "";
}

/** A retired subpage (`/admin/settings/tools`) → the page that replaced it, or "" if none. */
export function settingsSectionAlias(section: string): string {
  return ALIASES[section] ?? "";
}

/** The first path segment below `settings/`; anything deeper is ignored. */
export function settingsSectionFromSubPath(subPath: string): string {
  return subPath.split("/")[0] ?? "";
}
