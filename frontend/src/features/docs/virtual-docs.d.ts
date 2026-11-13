declare module "virtual:spaceworks-docs" {
  const entries: import("./docsTypes").DocEntry[];
  export default entries;
}

declare module "virtual:spaceworks-docs-pages" {
  /** One lazy loader per published page, keyed by its path under docs/. */
  export const loaders: Record<string, () => Promise<{ default: string }>>;
}
