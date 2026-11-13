// Virtual modules served by scripts/api-reference-plugin.ts (see that file for what each holds).
declare module "virtual:spaceworks-api-index" {
  const index: import("./apiReferenceModel").ApiIndexEntry[];
  export default index;
  export const tags: import("./apiReferenceModel").ApiTagSummary[];
  export const version: string;
}

declare module "virtual:spaceworks-api-tags" {
  export const tags: import("./apiReferenceModel").ApiTagSummary[];
  export const version: string;
  export const loaders: { [slug: string]: () => Promise<{ default: import("./apiReferenceModel").ApiTagPayload }> };
}

declare module "virtual:spaceworks-api-tag/*" {
  const payload: import("./apiReferenceModel").ApiTagPayload;
  export default payload;
}
