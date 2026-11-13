import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { buildDocsIndex, resolveDocsDir, selectedSources } from "../../../scripts/docs-plugin";

const temps: string[] = [];
afterEach(() => { temps.splice(0).forEach(dir => rmSync(dir, { recursive: true, force: true })); });
const temp = (prefix: string) => { const dir = mkdtempSync(join(tmpdir(), prefix)); temps.push(dir); return dir; };

function fixture() {
  const root = temp("sw-docs-");
  const docs = join(root, "docs");
  mkdirSync(join(docs, "hosting"), { recursive: true });
  mkdirSync(join(docs, "modules"), { recursive: true });
  writeFileSync(join(docs, "hosting", "docker.md"), "---\ntitle: Docker\ngroup: Hosting\norder: 2\nsummary: Run it with Compose.\nupdated: 2026-11-10\n---\n# Docker\n\nIntro.\n\n## Install\n\n```sh\n# not a heading\n```\n\n### Check `it` works\n\n## Install\n");
  writeFileSync(join(docs, "modules", "README.md"), "---\ntitle: Modules\n---\nAll areas.\n");
  writeFileSync(join(docs, "MODULES.md"), "# SpaceWorks modules\n\nEvery module key.\n");
  writeFileSync(join(docs, "INVARIANTS.md"), "# Internal\n");
  writeFileSync(join(docs, "README.md"), "- [Modules](MODULES.md) — every module key, explained.\n");
  return { root, docs };
}

describe("docs build index (read straight from docs/)", () => {
  it("publishes the docs-site folders and curated guides, never internal notes or the README", () => {
    const { docs } = fixture();
    expect(selectedSources(docs).sort()).toEqual(["MODULES.md", "hosting/docker.md", "modules/README.md"]);
    expect(selectedSources("")).toEqual([]);
  });

  it("finds ../docs first, then a docs-snapshot copy, then nothing", () => {
    const { root } = fixture();
    const frontend = join(root, "frontend");
    mkdirSync(frontend);
    expect(resolveDocsDir(frontend, "")).toBe(join(root, "docs"));
    const lone = temp("sw-front-");
    expect(resolveDocsDir(lone, "")).toBe("");
    mkdirSync(join(lone, "docs-snapshot"));
    expect(resolveDocsDir(lone, "")).toBe(join(lone, "docs-snapshot"));
  });

  it("reads front matter, falls back to the README summary and keeps anchors unique", () => {
    const { docs } = fixture();
    const index = buildDocsIndex(docs);
    const docker = index.find(entry => entry.id === "hosting/docker")!;
    expect(docker).toMatchObject({ title: "Docker", group: "Hosting", order: 2, summary: "Run it with Compose.", updated: "2026-11-10" });
    expect(docker.headings).toEqual([
      { depth: 2, text: "Install", id: "install" },
      { depth: 3, text: "Check it works", id: "check-it-works" },
      { depth: 2, text: "Install", id: "install-1" },
    ]);
    // The folder page owns "modules"; the curated MODULES.md moves aside instead of colliding.
    expect(index.find(entry => entry.source === "modules/README.md")).toMatchObject({ id: "modules", group: "Areas & modules" });
    expect(index.find(entry => entry.source === "MODULES.md"))
      .toMatchObject({ id: "modules-reference", group: "Areas & modules", title: "SpaceWorks modules", summary: "Every module key, explained." });
  });
});
