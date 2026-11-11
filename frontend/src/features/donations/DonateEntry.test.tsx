import { describe, expect, it } from "vitest";

import type { TenantBootstrap } from "../../lib/api";
import { publicPageChrome } from "../inventory/PublicPageChrome";
import { isDonationPath } from "./routeNames";

// Decision 242(m): a non-profit taking gifts gets a Donate entry on every public page; others get none.
const bootstrap = (donate: boolean) => ({
  makerspace: { name: "Lab", slug: "lab", logo_url: "", ...(donate ? { donate_enabled: true } : {}) },
  modules: [], features: [], branding: {},
}) as unknown as TenantBootstrap;
const path = (part = "") => `/m/lab/${part}`;

describe("public Donate entry", () => {
  it("shows in the nav and footer for a non-profit taking gifts", () => {
    const chrome = publicPageChrome("lab", "Lab", path, bootstrap(true));
    expect(chrome.nav).toContainEqual({ label: "Donate", href: "/m/lab/donate" });
    expect(chrome.footer.links).toContainEqual({ label: "Support this space", href: "/m/lab/donate" });
  });

  it("is absent otherwise", () => {
    const chrome = publicPageChrome("lab", "Lab", path, bootstrap(false));
    expect(chrome.nav.map(link => link.label)).not.toContain("Donate");
    expect(chrome.footer.links.map(link => link.label)).not.toContain("Support this space");
  });

  it("routes a campaign's own page to the giving pages", () => {
    expect(isDonationPath("/m/lab/donate/campaign/laser")).toBe(true);
    expect(isDonationPath("/donate/campaign/laser")).toBe(true);
    expect(isDonationPath("/m/lab/donate/campaign")).toBe(false);
  });
});
