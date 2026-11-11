import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { API_REFERENCE_PATH, findDoc } from "../docs/docsIndex";
import { DOCS_LINKS, HUB_VERSION, LICENSE_SPDX, LICENSE_URL } from "./hubLinks";

// Vitest runs from frontend/, one level below the repository root.
const repo = resolve(process.cwd(), "..");

// Every fixed docs address the hub links to must be a page the in-app docs index publishes, so a
// renamed or dropped Markdown file fails here instead of shipping a "Page not found" from the landing.
describe("hub links", () => {
  const pages = Object.entries(DOCS_LINKS).flatMap(([name, value]): [string, string][] => typeof value === "string" ? [[name, value]] : []);

  it.each(pages)("%s (%s) resolves inside the app", (_name, href) => {
    expect(href.startsWith("/docs")).toBe(true);
    const [path] = href.split("#");
    if (path === "/docs" || path === API_REFERENCE_PATH) return;
    expect(findDoc(path.slice("/docs/".length)), `${href} is not a published docs page`).toBeDefined();
  });

  it("points the licence and project pages at the docs written for them", () => {
    expect(findDoc("project/license")?.title).toBe("License");
    expect(findDoc("project/third-party")?.title).toBe("Third-party software and fonts");
    expect(findDoc("project/security-policy")?.title).toBe("Security policy");
    expect(findDoc("project/contributing")?.title).toBe("Contributing");
    expect(DOCS_LINKS.apiReference).toBe(API_REFERENCE_PATH);
  });

  it("names the licence the LICENSE file carries", () => {
    const license = readFileSync(resolve(repo, "LICENSE"), "utf8");
    expect(license).toContain("GNU AFFERO GENERAL PUBLIC LICENSE");
    expect(LICENSE_SPDX).toBe("AGPL-3.0-or-later");
    expect(LICENSE_URL).toBe("https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/LICENSE");
  });

  it("takes the version from the repository VERSION file at build time", () => {
    const version = readFileSync(resolve(repo, "VERSION"), "utf8").trim();
    expect(HUB_VERSION).toBe(version);
  });

  it("builds a docs search address", () => {
    expect(DOCS_LINKS.search("backup & restore")).toBe("/docs?q=backup%20%26%20restore");
  });
});
