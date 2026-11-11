import type { DocsSearchHit } from "../docsTypes";
import type { ApiIndexEntry, ApiTagSummary } from "./apiReferenceModel";

type Indexed = { entry: ApiIndexEntry; tag: ApiTagSummary | undefined; text: string };
let indexed: Promise<Indexed[]> | null = null;

// The operation index (~2,500 entries) is its own chunk, fetched the first time anyone searches.
function load() {
  indexed ??= import("virtual:spaceworks-api-index").then(module => {
    const tags = new Map(module.tags.map(tag => [tag.slug, tag]));
    return module.default.map(entry => {
      const tag = tags.get(entry.tag);
      return { entry, tag, text: [entry.summary, entry.path, entry.operationId, entry.method, tag?.name ?? ""].join(" ").toLowerCase() };
    });
  }).catch(error => { indexed = null; throw error; });
  return indexed;
}

/** Every word must appear in the summary, path, operation id, method or section name. Summary hits rank first. */
export async function searchApiOperations(query: string, limit = 8): Promise<DocsSearchHit[]> {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const rows = await load();
  const matches = rows.filter(row => words.every(word => row.text.includes(word)));
  const score = (row: Indexed) => (words.every(word => row.entry.summary.toLowerCase().includes(word)) ? 0 : 1);
  return matches.sort((a, b) => score(a) - score(b)).slice(0, limit).map(({ entry }) => ({
    id: `api:${entry.operationId}`,
    kind: "operation",
    title: entry.summary || entry.operationId,
    context: `${entry.method} ${entry.path}`,
    href: `/docs/api/reference/${entry.tag}#${entry.operationId}`,
  }));
}
