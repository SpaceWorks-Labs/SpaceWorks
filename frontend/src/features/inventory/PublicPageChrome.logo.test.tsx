import { describe, expect, it } from "vitest";
import type { TenantBootstrap } from "../../lib/api";
import { publicPageChrome } from "./PublicPageChrome";

// #210: every public tenant page (home, Inventory, Shop, events, bookings, machines, stats) builds its header
// from this one helper, so the uploaded logo reaches all of them or none.
const path = (part?: string) => `/m/lab${part ? `/${part}` : ""}`;
const boot = (logo: string) => ({ modules: ["public_inventory", "events", "bookings", "machines", "shop"], features: ["shop.online", "loans.enabled"],
  makerspace: { name: "Lab", slug: "lab", logo_url: logo, public_stats_enabled: true }, branding: {} }) as unknown as TenantBootstrap;

describe("shared public chrome (#210)", () => {
  it("passes the uploaded tenant logo and the tenant home link to the header", () => {
    const chrome = publicPageChrome("lab", "Lab", path, boot("/public-images/lab/logo.webp"));
    expect(chrome.makerspace).toEqual({ slug: "lab", name: "Lab", logo: "/public-images/lab/logo.webp", homeHref: "/m/lab" });
    expect(chrome.nav.map(link => link.label)).toEqual(["Home", "Inventory", "Events", "Machines", "Book a space", "Shop", "Stats"]);
  });

  it("leaves the logo unset without an upload so the header shows the symbol and name", () => {
    expect(publicPageChrome("lab", "Lab", path, boot("")).makerspace.logo).toBeUndefined();
  });
});
