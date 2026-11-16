import type { HelpArticle } from "./helpTypes";

// Article files are Markdown with a small front matter block:
//
//   ---
//   title: Borrow a tool
//   summary: One sentence for lists and search results.
//   order: 20
//   keywords: loan, request, pickup
//   modules: request_workflow          (optional: any one must be on in the space)
//   features: inventory.self_checkout  (optional: any one must be on in the space)
//   actions: manage_id_programmes      (optional: also shown to holders of these actions)
//   ---
//
// The folder is the locale, then the section: `src/help-content/en/member/borrow.md` is the
// article `member/borrow`. A translation adds `src/help-content/<locale>/...` with the same
// paths (L9); a missing translation falls back to English, article by article.

export const DEFAULT_LOCALE = "en";

const RAW_FILES = import.meta.glob("../../help-content/*/*/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

const list = (value: string | undefined) => (value ?? "").split(",").map(item => item.trim()).filter(Boolean);

/** Split `---` front matter from the body. Unknown keys are ignored; a file without it is skipped. */
export function parseArticle(path: string, raw: string): { locale: string; article: HelpArticle } | null {
  const match = /help-content\/([^/]+)\/([^/]+)\/([^/]+)\.md$/.exec(path);
  const text = raw.replace(/\r\n?/g, "\n");
  const front = /^---\n([\s\S]*?)\n---\n?/.exec(text);
  if (!match || !front) return null;
  const meta: Record<string, string> = {};
  for (const line of front[1].split("\n")) {
    const colon = line.indexOf(":");
    if (colon > 0) meta[line.slice(0, colon).trim()] = line.slice(colon + 1).trim();
  }
  const [, locale, section, slug] = match;
  if (!meta.title) return null;
  return {
    locale,
    article: {
      id: `${section}/${slug}`, section, slug, title: meta.title, summary: meta.summary ?? "",
      order: Number(meta.order) || 100, keywords: list(meta.keywords), actions: list(meta.actions),
      modules: list(meta.modules), features: list(meta.features), body: text.slice(front[0].length).trim(),
    },
  };
}

function buildCatalogue(files: Record<string, string>) {
  const byLocale = new Map<string, Map<string, HelpArticle>>();
  for (const [path, raw] of Object.entries(files)) {
    const parsed = parseArticle(path, raw);
    if (!parsed) continue;
    if (!byLocale.has(parsed.locale)) byLocale.set(parsed.locale, new Map());
    byLocale.get(parsed.locale)!.set(parsed.article.id, parsed.article);
  }
  return byLocale;
}

const CATALOGUE = buildCatalogue(RAW_FILES);

const byOrder = (a: HelpArticle, b: HelpArticle) => a.order - b.order || a.title.localeCompare(b.title);

/** Every article in the locale, English filling any gap, sorted by section order then `order`. */
export function helpArticles(locale = DEFAULT_LOCALE): HelpArticle[] {
  const merged = new Map(CATALOGUE.get(DEFAULT_LOCALE) ?? []);
  if (locale !== DEFAULT_LOCALE) for (const [id, article] of CATALOGUE.get(locale) ?? []) merged.set(id, article);
  return [...merged.values()].sort(byOrder);
}

export function helpArticle(id: string, locale = DEFAULT_LOCALE): HelpArticle | undefined {
  return CATALOGUE.get(locale)?.get(id) ?? CATALOGUE.get(DEFAULT_LOCALE)?.get(id);
}
