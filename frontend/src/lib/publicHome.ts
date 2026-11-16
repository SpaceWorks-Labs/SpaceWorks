import type { TenantBootstrap } from "./api";

export type PublicFamily = "inventory" | "events" | "bookings" | "machines" | "membership";
/** Every published tenant root is an overview; inventory owns its separate route. */
export type PublicHome = "makerspace" | "none";

const ORDER = ["inventory", "events", "bookings", "machines", "membership"] as const;

/** The public families this tenant actually serves, in display order. */
export function publicFamilies(bootstrap: TenantBootstrap): PublicFamily[] {
  if (bootstrap.makerspace.public_site_enabled === false) return [];
  const modules = new Set(bootstrap.modules);
  const available: Record<PublicFamily, boolean> = {
    inventory: modules.has("public_inventory") && bootstrap.features.includes("loans.enabled")
      && bootstrap.makerspace.public_inventory_enabled !== false,
    events: modules.has("events"),
    bookings: modules.has("bookings"),
    machines: modules.has("machines"),
    membership: modules.has("membership"),
  };
  return ORDER.filter((family) => available[family]);
}

/** Published tenant roots share one overview, independent of the chosen shortcut or edition. */
export function publicHome(bootstrap: TenantBootstrap): PublicHome {
  return bootstrap.makerspace.public_site_enabled === false ? "none" : "makerspace";
}

/** Preserve a saved family's intent as the overview's primary shortcut, only while available. */
export function preferredPublicFamily(bootstrap: TenantBootstrap): PublicFamily | undefined {
  const families = publicFamilies(bootstrap);
  const selected = bootstrap.makerspace.public_landing_page;
  return selected && selected !== "auto" && families.includes(selected) ? selected : undefined;
}
