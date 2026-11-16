import { t } from "@lingui/core/macro";
import entries from "virtual:spaceworks-docs";
import { DOC_GROUPS } from "../../../scripts/docs-manifest";
import type { DocEntry, DocsSearchHit } from "./docsTypes";

export const DOCS_VERSION = __SPACEWORKS_VERSION__;
export const REPO_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks";
/** Kept here, not imported from the API reference, so the docs chunk never pulls that code in. */
export const API_REFERENCE_PATH = "/docs/api/reference";

/** Sidebar labels for the fixed groups; a group a docs page invents shows as written. */
export function groupLabel(group: string) {
  const labels: Record<string, string> = {
    "Getting started": t`Getting started`, Tutorials: t`Tutorials`, "User guides": t`User guides`,
    "How-to guides": t`How-to guides`, "Areas & modules": t`Areas & modules`, Architecture: t`Architecture`,
    Hosting: t`Hosting`, API: t`API`, Reference: t`Reference`, Project: t`Project`, Changelog: t`Changelog`,
  };
  return labels[group] ?? group;
}

const rank = (group: string) => {
  const index = (DOC_GROUPS as readonly string[]).indexOf(group);
  return index < 0 ? DOC_GROUPS.length : index;
};

export type DocGroup = { name: string; pages: DocEntry[] };

/** Groups in sidebar order, pages by `order` then title. */
export function docGroups(source: readonly DocEntry[] = entries): DocGroup[] {
  const byGroup = new Map<string, DocEntry[]>();
  for (const entry of source) byGroup.set(entry.group, [...(byGroup.get(entry.group) ?? []), entry]);
  return [...byGroup.entries()]
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
    .map(([name, pages]) => ({ name, pages: [...pages].sort((a, b) => a.order - b.order || a.title.localeCompare(b.title)) }));
}

/** Reading order: the sidebar flattened, for previous/next links. */
export function readingOrder(source: readonly DocEntry[] = entries) {
  return docGroups(source).flatMap(group => group.pages);
}

export function findDoc(id: string, source: readonly DocEntry[] = entries) {
  const clean = id.replace(/\/+$/, "").toLowerCase();
  return source.find(entry => entry.id === clean);
}

export function neighbours(id: string, source: readonly DocEntry[] = entries) {
  const order = readingOrder(source);
  const index = order.findIndex(entry => entry.id === id);
  return { previous: index > 0 ? order[index - 1] : undefined, next: index >= 0 ? order[index + 1] : undefined };
}

export const allDocs: readonly DocEntry[] = entries;

const normalize = (value: string) => value.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").trim();

/**
 * Every query word must appear in the candidate; titles outrank headings, headings outrank summaries,
 * and a word at the start of the title outranks one in the middle.
 */
export function searchDocs(query: string, limit = 12, source: readonly DocEntry[] = entries): DocsSearchHit[] {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const scored: { hit: DocsSearchHit; score: number }[] = [];
  const score = (text: string, weight: number) => {
    const value = normalize(text);
    if (!words.every(word => value.includes(word))) return 0;
    return weight + (value.startsWith(words[0]) ? 3 : 0) + (value === words.join(" ") ? 5 : 0);
  };
  for (const entry of source) {
    const page = Math.max(score(entry.title, 30), score(`${entry.title} ${entry.summary}`, 12), score(`${entry.title} ${entry.group}`, 8));
    if (page) scored.push({ score: page, hit: { id: entry.id, kind: "page", title: entry.title, context: entry.summary || groupLabel(entry.group), href: `/docs/${entry.id}` } });
    for (const heading of entry.headings) {
      const value = score(heading.text, heading.depth === 2 ? 18 : 14) || score(`${entry.title} ${heading.text}`, 6);
      if (value) scored.push({ score: value, hit: { id: `${entry.id}#${heading.id}`, kind: "heading", title: heading.text, context: entry.title, href: `/docs/${entry.id}#${heading.id}` } });
    }
  }
  return scored.sort((a, b) => b.score - a.score || a.hit.title.localeCompare(b.hit.title)).slice(0, limit).map(item => item.hit);
}

/** Stable anchor for a group's section on /docs: "Areas & modules" → "areas-modules". */
export function groupAnchor(group: string) {
  return group.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
