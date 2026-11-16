import { afterEach, describe, expect, it } from "vitest";
import { applyTenantBranding } from "./branding";

const originalHead = document.head.innerHTML;
afterEach(() => { document.head.innerHTML = originalHead; });

function apply(logo: string) {
  applyTenantBranding({
    branding: { display_name: "Forge" }, makerspace: { name: "Forge" },
    theme: { logo_url: logo },
  } as unknown as Parameters<typeof applyTenantBranding>[0]);
}

describe("brand favicon with PNG fallbacks", () => {
  it("keeps the tenant favicon preferred and resets the same link to the app icon", () => {
    document.head.innerHTML = `<link rel="icon" type="image/svg+xml" href="/brand/favicon.svg">
      <link rel="icon" type="image/png" sizes="32x32" href="/brand/icon-32.png">
      <link rel="icon" type="image/png" sizes="16x16" href="/brand/icon-16.png">`;
    apply("/tenant.png");
    const selected = document.querySelector<HTMLLinkElement>("[data-spaceworks-favicon]")!;
    expect(document.head.lastElementChild).toBe(selected);
    expect(selected.getAttribute("href")).toBe("/tenant.png");
    expect(selected.hasAttribute("type")).toBe(false);
    apply("");
    expect(document.head.lastElementChild).toBe(selected);
    expect(selected.getAttribute("href")).toBe("/brand/favicon.svg");
    expect(document.querySelectorAll('[rel="icon"]')).toHaveLength(3);
  });

  it("creates a favicon when the page has none", () => {
    document.head.innerHTML = "";
    apply("");
    expect(document.querySelector('[rel="icon"]')?.getAttribute("href")).toBe("/brand/favicon.svg");
  });
});
