import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import type { Plugin, ViteDevServer } from "vite";
import { documentTitle, extractHeadings, firstParagraph, parseFrontMatter } from "../src/features/docs/docsSource";
import { CURATED_DOCS, DOC_FOLDERS, TITLE_OVERRIDES, docId } from "./docs-manifest";

// The in-app /docs reads the repository's docs/ folder directly at dev, test and build time. Nothing
// is copied into src/ and nothing is edited by hand: change docs/ and the pages follow.
//
// The frontend image is built with ./frontend as its Docker context, where ../docs does not exist.
// For that build only, `node scripts/docs-snapshot.mjs` (run by the release workflow before
// `docker build`) copies docs/ into frontend/docs-snapshot/, which is git-ignored. Order of lookup:
// SPACEWORKS_DOCS_DIR, ../docs, ./docs-snapshot. With none of them the docs pages build empty.
//
// Virtual modules:
//   virtual:spaceworks-docs        the index: id, source, group, order, title, summary, headings
//   virtual:spaceworks-docs-pages  `loaders[source]()` → one lazily loaded chunk per page body
//   virtual:spaceworks-doc/<src>   one page's raw Markdown

const INDEX = "virtual:spaceworks-docs";
const PAGES = "virtual:spaceworks-docs-pages";
const PAGE = "virtual:spaceworks-doc/";

function walk(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : name.toLowerCase().endsWith(".md") ? [path] : [];
  });
}

const posix = (path: string) => path.split(sep).join("/");

export function resolveDocsDir(root: string, env = process.env.SPACEWORKS_DOCS_DIR) {
  const candidates = [env ? resolve(root, env) : "", resolve(root, "../docs"), resolve(root, "docs-snapshot")].filter(Boolean);
  return candidates.find(dir => existsSync(dir)) ?? "";
}

/** Every published page (relative to docs/): the docs-site folders whole, plus the curated guides. */
export function selectedSources(docs: string) {
  if (!docs) return [];
  const folders = Object.keys(DOC_FOLDERS).flatMap(folder => walk(join(docs, folder)).map(file => posix(relative(docs, file))));
  const curated = CURATED_DOCS.map(doc => doc.source).filter(source => existsSync(join(docs, source)));
  return [...new Set([...folders, ...curated])];
}

/** `[Title](file.md) — description` bullets in docs/README.md, keyed by source path. */
function readmeSummaries(docs: string) {
  const path = join(docs, "README.md");
  const summaries = new Map<string, string>();
  if (!docs || !existsSync(path)) return summaries;
  for (const match of readFileSync(path, "utf8").matchAll(/^- \[[^\]]+\]\(([^)#\s]+\.md)\)[^—\n]*—\s*(.+)$/gm)) {
    const text = match[2].replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").trim();
    summaries.set(match[1], text.charAt(0).toUpperCase() + text.slice(1));
  }
  return summaries;
}

export function buildDocsIndex(docs: string) {
  const summaries = readmeSummaries(docs);
  const curated = new Map(CURATED_DOCS.map((doc, index) => [doc.source, { ...doc, index }]));
  const sources = selectedSources(docs);
  const taken = new Set<string>();
  // Folder pages claim their ids first; a curated page that collides gets a "-reference" suffix.
  const ordered = [...sources.filter(source => !curated.has(source)), ...sources.filter(source => curated.has(source))];
  return ordered.map(source => {
    const raw = readFileSync(join(docs, source), "utf8");
    const { data, body } = parseFrontMatter(raw);
    const pick = curated.get(source);
    const folderGroup = source.includes("/") ? DOC_FOLDERS[source.split("/")[0]] : undefined;
    let id = docId(source);
    if (taken.has(id)) id = `${id}-reference`;
    taken.add(id);
    const order = Number(data.order);
    return {
      id, source,
      group: data.group || folderGroup || pick?.group || "Reference",
      order: data.order !== undefined && Number.isFinite(order) ? order : 1000 + (pick?.index ?? 0),
      title: data.title || TITLE_OVERRIDES[source] || documentTitle(body) || source.replace(/\.md$/, ""),
      summary: data.summary || summaries.get(source) || firstParagraph(body),
      ...(data.updated ? { updated: data.updated } : {}),
      headings: extractHeadings(raw),
    };
  });
}

export function docsContent(): Plugin {
  let docs = "";
  const invalidate = (server: ViteDevServer, file: string) => {
    const source = posix(relative(docs, file));
    for (const id of [`\0${INDEX}`, `\0${PAGES}`, `\0${PAGE}${source}`]) {
      const module = server.moduleGraph.getModuleById(id);
      if (module) server.moduleGraph.invalidateModule(module);
    }
    server.ws.send({ type: "full-reload" });
  };
  return {
    name: "spaceworks-docs-content",
    configResolved(config) {
      docs = resolveDocsDir(config.root);
      if (!docs) config.logger.warn("[spaceworks-docs] no docs folder found: /docs will be empty (run scripts/docs-snapshot.mjs)");
    },
    configureServer(server) {
      if (!docs) return;
      server.watcher.add(docs);
      const onChange = (file: string) => { if (file.startsWith(docs) && file.toLowerCase().endsWith(".md")) invalidate(server, file); };
      server.watcher.on("add", onChange).on("change", onChange).on("unlink", onChange);
    },
    resolveId(id) {
      if (id === INDEX || id === PAGES || id.startsWith(PAGE)) return `\0${id}`;
      return undefined;
    },
    load(id) {
      if (id === `\0${INDEX}`) return `export default ${JSON.stringify(buildDocsIndex(docs))};`;
      if (id === `\0${PAGES}`) {
        const lines = selectedSources(docs).map(source => `  ${JSON.stringify(source)}: () => import(${JSON.stringify(PAGE + source)}),`);
        return `export const loaders = {\n${lines.join("\n")}\n};`;
      }
      if (id.startsWith(`\0${PAGE}`)) {
        const source = id.slice(`\0${PAGE}`.length);
        if (!selectedSources(docs).includes(source)) throw new Error(`Unpublished docs page: ${source}`);
        const file = join(docs, source);
        this.addWatchFile(file);
        return `export default ${JSON.stringify(readFileSync(file, "utf8"))};`;
      }
      return undefined;
    },
  };
}
