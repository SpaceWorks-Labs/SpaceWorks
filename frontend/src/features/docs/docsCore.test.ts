import { describe, expect, it } from "vitest";
import { docGroups, groupAnchor, neighbours, readingOrder, searchDocs } from "./docsIndex";
import { resolveDocLink } from "./docsLinks";
import { articleBody, extractHeadings, parseFrontMatter, slugify } from "./docsSource";
import type { DocEntry } from "./docsTypes";

const doc = (id: string, source: string, group: string, order: number, title: string, extra: Partial<DocEntry> = {}): DocEntry =>
  ({ id, source, group, order, title, summary: "", headings: [], ...extra });

const INDEX: DocEntry[] = [
  doc("hosting/docker", "hosting/docker.md", "Hosting", 2, "Docker Compose", { summary: "Run the stack with Compose.",
    headings: [{ depth: 2, text: "Back up the volumes", id: "back-up-the-volumes" }] }),
  doc("hosting/install", "hosting/install.md", "Hosting", 1, "Quick install"),
  doc("guide/overview", "guide/overview.md", "Getting started", 1, "What Space Works is"),
  doc("install-and-update", "install-and-update.md", "Hosting", 1001, "Install and update"),
  doc("custom/page", "custom/page.md", "Zines", 1, "A group nobody planned"),
];

describe("docs index", () => {
  it("orders groups by the sidebar list, unknown groups last, pages by order then title", () => {
    expect(docGroups(INDEX).map(group => group.name)).toEqual(["Getting started", "Hosting", "Zines"]);
    expect(docGroups(INDEX)[1].pages.map(page => page.id)).toEqual(["hosting/install", "hosting/docker", "install-and-update"]);
    expect(groupAnchor("Areas & modules")).toBe("areas-modules");
  });

  it("links previous and next in reading order across groups", () => {
    expect(readingOrder(INDEX).map(page => page.id)[0]).toBe("guide/overview");
    expect(neighbours("hosting/install", INDEX)).toMatchObject({ previous: { id: "guide/overview" }, next: { id: "hosting/docker" } });
    expect(neighbours("guide/overview", INDEX).previous).toBeUndefined();
    expect(neighbours("custom/page", INDEX).next).toBeUndefined();
  });

  it("searches titles, summaries and headings, every word must match", () => {
    const hits = searchDocs("docker", 10, INDEX);
    expect(hits[0]).toMatchObject({ kind: "page", href: "/docs/hosting/docker" });
    expect(searchDocs("back up volumes", 10, INDEX)).toEqual([
      expect.objectContaining({ kind: "heading", title: "Back up the volumes", href: "/docs/hosting/docker#back-up-the-volumes", context: "Docker Compose" }),
    ]);
    expect(searchDocs("compose stack", 10, INDEX).map(hit => hit.id)).toContain("hosting/docker");
    expect(searchDocs("kubernetes", 10, INDEX)).toEqual([]);
    expect(searchDocs("   ", 10, INDEX)).toEqual([]);
  });
});

describe("doc links", () => {
  it("keeps links between published pages inside the app", () => {
    expect(resolveDocLink("docker.md#ports", "hosting/install.md", INDEX)).toEqual({ kind: "internal", to: "/docs/hosting/docker#ports" });
    expect(resolveDocLink("../install-and-update.md", "hosting/docker.md", INDEX)).toEqual({ kind: "internal", to: "/docs/install-and-update" });
    expect(resolveDocLink("./hosting/docker.md", "install-and-update.md", INDEX)).toEqual({ kind: "internal", to: "/docs/hosting/docker" });
    expect(resolveDocLink("#options", "hosting/docker.md", INDEX)).toEqual({ kind: "anchor", hash: "options" });
  });

  it("sends unpublished docs and other repository files to GitHub, and leaves web links alone", () => {
    expect(resolveDocLink("INVARIANTS.md#money", "install-and-update.md", INDEX))
      .toEqual({ kind: "external", href: "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/docs/INVARIANTS.md#money" });
    expect(resolveDocLink("../.github/SECURITY.md", "install-and-update.md", INDEX))
      .toEqual({ kind: "external", href: "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/.github/SECURITY.md" });
    expect(resolveDocLink("../brand/symbol.svg", "hosting/docker.md", INDEX))
      .toEqual({ kind: "external", href: "https://github.com/SpaceWorks-Labs/SpaceWorks/raw/main/docs/brand/symbol.svg" });
    expect(resolveDocLink("https://example.org/x", "hosting/docker.md", INDEX)).toEqual({ kind: "external", href: "https://example.org/x" });
    expect(resolveDocLink("mailto:security@example.org", "hosting/docker.md", INDEX).kind).toBe("external");
  });
});

describe("markdown source helpers", () => {
  it("strips front matter and the leading title, and anchors headings like GitHub", () => {
    const raw = "---\ntitle: \"Quoted: title\"\norder: 3\n---\n# Title\n\nBody\n\n## Set up `HTTPS` & DNS\n\n```sh\n## not a heading\n```\n\n## Set up HTTPS DNS\n";
    expect(parseFrontMatter(raw).data).toEqual({ title: "Quoted: title", order: "3" });
    expect(articleBody(raw).startsWith("\nBody")).toBe(true);
    expect(slugify("Path 1: guided install (easiest)")).toBe("path-1-guided-install-easiest");
    expect(extractHeadings(raw).map(heading => heading.id)).toEqual(["set-up-https--dns", "set-up-https-dns"]);
  });
});
