import { describe, expect, it } from "vitest";
import { FEATURE_DEFINITIONS } from "../../lib/features";
import { STAFF_TAB_KEYS } from "../staff/staffAccess";
import { helpArticle, helpArticles, parseArticle } from "./helpContent";
import { helpHref } from "./helpPaths";
import { helpLinkTargets, parseHelpBlocks } from "./helpMarkdown";
import { HELP_SCREENSHOTS } from "./helpScreenshots";
import { SECTION_BY_ID } from "./helpSections";
import { STAFF_SCREEN_HELP } from "./staffScreenHelp";

const articles = helpArticles();

// Capability keys from release-2 lanes that are not in this base yet. Each article naming one is
// hidden in a space until the lane merges and the space switches it on. Empty this list as they land.
const PENDING_LANE_FEATURES = new Set<string>([]);
// Staff tabs with no article of their own.
const UNMAPPED_TABS = new Set<string>([]);

describe("help content", () => {
  it("parses every content file, with a known section and a unique id", () => {
    expect(articles.length).toBeGreaterThan(100);
    expect(new Set(articles.map(article => article.id)).size).toBe(articles.length);
    for (const article of articles) expect(SECTION_BY_ID.has(article.section), article.id).toBe(true);
  });

  it("gives every article numbered steps, a who-can-do-this note and an editorial screenshot slot", () => {
    for (const article of articles) {
      const blocks = parseHelpBlocks(article.body);
      expect(blocks.some(block => block.kind === "steps"), `${article.id} steps`).toBe(true);
      expect(blocks.some(block => block.kind === "screenshot"), `${article.id} screenshot`).toBe(true);
      expect(article.body, `${article.id} who note`).toMatch(/\*\*Who can do this:\*\*/);
      expect(article.summary, `${article.id} summary`).not.toBe("");
    }
  });

  it("maps reviewed screenshots only to real editorial keys with usable image dimensions", () => {
    const keys = new Set(articles.flatMap(article => parseHelpBlocks(article.body).flatMap(block => block.kind === "screenshot" ? [block.key] : [])));
    for (const [key, image] of Object.entries(HELP_SCREENSHOTS)) {
      expect(keys.has(key), key).toBe(true);
      expect(image.src, key).not.toBe("");
      expect(image.width, key).toBeGreaterThan(0);
      expect(image.height, key).toBeGreaterThan(0);
    }
  });

  it("resolves every deep link between articles", () => {
    for (const article of articles) {
      for (const target of helpLinkTargets(article.body)) expect(helpArticle(target), `${article.id} -> ${target}`).toBeDefined();
    }
  });

  it("gives every staff console screen a Help link that resolves", () => {
    for (const tab of STAFF_TAB_KEYS) {
      if (UNMAPPED_TABS.has(tab)) continue;
      expect(STAFF_SCREEN_HELP[tab], tab).toBeDefined();
    }
    for (const [tab, target] of Object.entries(STAFF_SCREEN_HELP)) expect(helpArticle(target), `${tab} -> ${target}`).toBeDefined();
  });

  it("names only real capability keys (or ones a release-2 lane is about to add)", () => {
    const known = new Set(FEATURE_DEFINITIONS.map(feature => feature.key));
    for (const article of articles) {
      for (const key of article.features) expect(known.has(key) || PENDING_LANE_FEATURES.has(key), `${article.id}: ${key}`).toBe(true);
    }
  });

  it("builds deep links for the platform, a central space and the platform session", () => {
    expect(helpHref("member/borrow-tools")).toBe("/help/member/borrow-tools");
    expect(helpHref("member/borrow-tools", { slug: "tinkerspace" })).toBe("/m/tinkerspace/help/member/borrow-tools");
    expect(helpHref("superadmin/platform-dashboard", { platform: true })).toBe("/help/superadmin/platform-dashboard?context=platform");
    expect(helpHref("", { slug: "tinkerspace" })).toBe("/m/tinkerspace/help");
  });

  it("falls back to English for a missing translation and skips files without front matter", () => {
    expect(helpArticles("xx").length).toBe(articles.length);
    expect(parseArticle("../../help-content/en/member/x.md", "no front matter")).toBeNull();
    const parsed = parseArticle("../../help-content/fr/member/x.md", "---\ntitle: Bonjour\nfeatures: a.b, c.d\n---\n1. Un");
    expect(parsed?.locale).toBe("fr");
    expect(parsed?.article.features).toEqual(["a.b", "c.d"]);
  });
});
