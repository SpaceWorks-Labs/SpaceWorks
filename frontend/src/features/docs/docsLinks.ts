import type { DocEntry } from "./docsTypes";

const REPO = "https://github.com/SpaceWorks-Labs/SpaceWorks";

export type ResolvedLink =
  | { kind: "internal"; to: string }
  | { kind: "anchor"; hash: string }
  | { kind: "external"; href: string };

/** Resolve `../a/./b.md` against a docs-relative directory; `..` past docs/ climbs into the repository. */
function join(fromDir: string, target: string) {
  const parts = ["docs", ...fromDir.split("/").filter(Boolean)];
  for (const part of target.split("/")) {
    if (part === "..") parts.pop();
    else if (part && part !== ".") parts.push(part);
  }
  return parts.join("/");
}

/**
 * Where a link written inside a docs page should go. Links to another published page stay in the
 * app (/docs/<id>#anchor); links to an unpublished doc or any other repository file open it on
 * GitHub; web links pass through untouched.
 */
export function resolveDocLink(href: string, fromSource: string, index: readonly DocEntry[]): ResolvedLink {
  const value = href.trim();
  if (value.startsWith("#")) return { kind: "anchor", hash: value.slice(1) };
  if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(value)) return { kind: "external", href: value };
  if (value.startsWith("/docs/") || value === "/docs") return { kind: "internal", to: value };
  const [pathPart, hash = ""] = value.split("#", 2);
  const [path] = pathPart.split("?", 1);
  const fromDir = fromSource.includes("/") ? fromSource.slice(0, fromSource.lastIndexOf("/")) : "";
  const repoPath = path.startsWith("/") ? path.slice(1) : join(fromDir, decodeURI(path));
  if (repoPath.startsWith("docs/")) {
    const docsPath = repoPath.slice("docs/".length);
    const target = index.find(entry => entry.source.toLowerCase() === docsPath.toLowerCase());
    if (target) return { kind: "internal", to: `/docs/${target.id}${hash ? `#${hash}` : ""}` };
  }
  const mode = /\.(png|jpe?g|gif|svg|webp|pdf)$/i.test(repoPath) ? "raw" : "blob";
  return { kind: "external", href: `${REPO}/${mode}/main/${repoPath}${hash ? `#${hash}` : ""}` };
}

export function editUrl(source: string) {
  return `${REPO}/edit/main/docs/${source}`;
}
