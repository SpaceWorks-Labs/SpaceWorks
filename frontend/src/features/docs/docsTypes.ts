/** One documentation page, as the build-time index (`virtual:spaceworks-docs`) describes it. */
export type DocHeading = { depth: 2 | 3; text: string; id: string };

export type DocEntry = {
  /** Route id under /docs/, e.g. "hosting/docker" or "reference/install-and-update". */
  id: string;
  /** Path of the source file relative to the repository's docs/ folder, e.g. "hosting/docker.md". */
  source: string;
  group: string;
  order: number;
  title: string;
  summary: string;
  /** From front matter `updated:` when present; never guessed. */
  updated?: string;
  headings: DocHeading[];
};

/** A command-palette result. Doc pages, their headings and API operations share one shape. */
export type DocsSearchHit = {
  id: string;
  kind: "page" | "heading" | "operation";
  title: string;
  /** The page title, group or HTTP method + path, shown under the title. */
  context: string;
  href: string;
};
