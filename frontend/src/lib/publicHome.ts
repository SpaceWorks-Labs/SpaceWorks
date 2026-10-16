import type { TenantBootstrap } from "./api";

export type PublicFamily = "inventory" | "events" | "bookings" | "machines" | "membership";
/** "makerspace" is the composed makerspace page (header, featured events, inventory, other sections). */
export type PublicHome = "makerspace" | Exclude<PublicFamily, "inventory"> | "none";

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

/**
 * A staff-chosen non-inventory family keeps its own full page, and so does a single-family tenant
 * (an events-only space still lands on its events list). Everything else gets the composed
 * makerspace page, which is where the catalogue now lives.
 */
export function publicHome(bootstrap: TenantBootstrap): PublicHome {
  const families = publicFamilies(bootstrap);
  if (!families.length) return "none";
  const selected = bootstrap.makerspace.public_landing_page;
  if (selected && selected !== "auto" && selected !== "inventory" && families.includes(selected)) return selected;
  const [only] = families;
  if (families.length === 1 && only !== "inventory") return only;
  return "makerspace";
}
