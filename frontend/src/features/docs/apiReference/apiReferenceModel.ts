// Pure build-time model of the API reference. The Vite plugin (scripts/api-reference-plugin.ts) runs it
// over frontend/openapi-schema.json; the browser only ever receives its small per-tag outputs.
// No DOM, Node or Lingui imports here: it is compiled by both the app and the node tsconfig.

export type SchemaNode = { [key: string]: unknown };
export type ApiParameter = { name: string; in: string; required: boolean; description?: string; schema?: SchemaNode };
export type ApiContent = { [mediaType: string]: SchemaNode | null };
export type ApiResponse = { status: string; description: string; content?: ApiContent };
export type ApiOperation = {
  operationId: string; method: string; path: string; summary: string; description?: string;
  /** Security scheme names that authorise the call; `anonymous` when `{}` is an alternative. */
  security: string[]; anonymous: boolean;
  parameters: ApiParameter[];
  requestBody?: { required: boolean; content: ApiContent };
  responses: ApiResponse[];
  /** Plain-language notes from the schema's x-free-form / x-request-body / x-response-body hints. */
  notes: { request?: string; response?: string; noRequestBody?: boolean; noResponseBody?: boolean };
};
export type ApiSecurityScheme = { type: string; description?: string; in?: string; name?: string; scheme?: string };
export type ApiTagSummary = { slug: string; name: string; description: string; group: string; count: number };
export type ApiIndexEntry = { tag: string; operationId: string; method: string; path: string; summary: string };
export type ApiTagPayload = {
  tag: ApiTagSummary; operations: ApiOperation[];
  schemas: { [name: string]: SchemaNode }; securitySchemes: { [name: string]: ApiSecurityScheme };
};
export type ApiReference = { version: string; index: ApiIndexEntry[]; tags: ApiTagSummary[]; payloads: { [slug: string]: ApiTagPayload } };

const METHODS = ["get", "post", "put", "patch", "delete", "head", "options"];
const REF_PREFIX = "#/components/schemas/";
const EXAMPLE_LIMIT = 400;

export function slugifyTag(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "tag";
}

/** A schema name from `#/components/schemas/Name`, or null for any other pointer. */
export function refName(ref: unknown) {
  return typeof ref === "string" && ref.startsWith(REF_PREFIX) ? ref.slice(REF_PREFIX.length) : null;
}

/** Drop `examples` and oversized `example` values: they are most of the bytes and none of the meaning. */
function lean(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(lean);
  if (!value || typeof value !== "object") return value;
  const out: SchemaNode = {};
  for (const [key, child] of Object.entries(value)) {
    if (key === "examples") continue;
    if (key === "example" && JSON.stringify(child ?? null).length > EXAMPLE_LIMIT) continue;
    out[key] = lean(child);
  }
  return out;
}

function collectRefs(value: unknown, into: Set<string>) {
  if (Array.isArray(value)) { value.forEach(item => collectRefs(item, into)); return; }
  if (!value || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value)) {
    const name = key === "$ref" ? refName(child) : null;
    if (name) into.add(name); else collectRefs(child, into);
  }
}

/** Every component schema reachable from `roots`, following $ref transitively; cycle-safe. */
export function reachableSchemas(roots: unknown, schemas: { [name: string]: SchemaNode }) {
  const pending = new Set<string>();
  collectRefs(roots, pending);
  const seen = new Set<string>();
  const queue = [...pending];
  while (queue.length) {
    const name = queue.pop()!;
    if (seen.has(name) || !schemas[name]) continue;
    seen.add(name);
    const next = new Set<string>();
    collectRefs(schemas[name], next);
    next.forEach(item => { if (!seen.has(item)) queue.push(item); });
  }
  const out: { [name: string]: SchemaNode } = {};
  [...seen].sort().forEach(name => { out[name] = lean(schemas[name]) as SchemaNode; });
  return out;
}

function content(raw: unknown): ApiContent | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const out: ApiContent = {};
  for (const [type, media] of Object.entries(raw as SchemaNode)) {
    const schema = (media as SchemaNode | null)?.schema;
    out[type] = schema ? lean(schema) as SchemaNode : null;
  }
  return Object.keys(out).length ? out : undefined;
}

function operation(path: string, method: string, op: SchemaNode, spec: SchemaNode): ApiOperation {
  const security = (op.security ?? spec.security ?? []) as SchemaNode[];
  const free = (op["x-free-form"] ?? {}) as { request?: string; response?: string };
  const body = op.requestBody as { required?: boolean; content?: unknown } | undefined;
  const responses = Object.entries((op.responses ?? {}) as SchemaNode).map(([status, raw]) => {
    const response = raw as { description?: string; content?: unknown };
    return { status, description: response.description ?? "", content: content(response.content) };
  });
  return {
    operationId: String(op.operationId), method: method.toUpperCase(), path,
    summary: String(op.summary ?? ""), description: op.description ? String(op.description) : undefined,
    security: [...new Set(security.flatMap(item => Object.keys(item)))],
    anonymous: security.some(item => !Object.keys(item).length),
    parameters: ((op.parameters ?? []) as SchemaNode[]).map(param => ({
      name: String(param.name), in: String(param.in), required: Boolean(param.required),
      description: param.description ? String(param.description) : undefined,
      schema: param.schema ? lean(param.schema) as SchemaNode : undefined,
    })),
    requestBody: body?.content ? { required: Boolean(body.required), content: content(body.content) ?? {} } : undefined,
    responses,
    notes: {
      request: free.request, response: free.response,
      noRequestBody: op["x-request-body"] === "none" || undefined,
      noResponseBody: op["x-response-body"] === "none" || undefined,
    },
  };
}

/** Tag order: x-tagGroups first (their group names travel with each tag), then declared tags, then A-Z. */
function orderedTags(spec: SchemaNode, used: Set<string>) {
  const groups = (spec["x-tagGroups"] ?? []) as { name: string; tags: string[] }[];
  const declared = (spec.tags ?? []) as { name: string; description?: string }[];
  const order: { name: string; group: string }[] = [];
  const placed = new Set<string>();
  const place = (name: string, group: string) => {
    if (!placed.has(name) && used.has(name)) { placed.add(name); order.push({ name, group }); }
  };
  groups.forEach(group => group.tags.forEach(name => place(name, group.name)));
  declared.forEach(tag => place(tag.name, ""));
  [...used].sort((a, b) => a.localeCompare(b)).forEach(name => place(name, ""));
  const descriptions = new Map(declared.map(tag => [tag.name, tag.description ?? ""]));
  return order.map(item => ({ ...item, description: descriptions.get(item.name) ?? "" }));
}

export function buildApiReference(spec: SchemaNode): ApiReference {
  const schemas = (((spec.components ?? {}) as SchemaNode).schemas ?? {}) as { [name: string]: SchemaNode };
  const schemes = (((spec.components ?? {}) as SchemaNode).securitySchemes ?? {}) as { [name: string]: ApiSecurityScheme };
  const byTag = new Map<string, ApiOperation[]>();
  for (const [path, item] of Object.entries((spec.paths ?? {}) as SchemaNode)) {
    for (const method of METHODS) {
      const op = (item as SchemaNode)[method] as SchemaNode | undefined;
      if (!op || typeof op !== "object" || !op.operationId) continue;
      const tags = ((op.tags as string[] | undefined)?.length ? op.tags : ["Other"]) as string[];
      // An operation listed under several tags appears on each tag page.
      for (const tag of tags) byTag.set(tag, [...(byTag.get(tag) ?? []), operation(path, method, op, spec)]);
    }
  }
  const slugs = new Set<string>();
  const tags: ApiTagSummary[] = orderedTags(spec, new Set(byTag.keys())).map(item => {
    let slug = slugifyTag(item.name);
    for (let n = 2; slugs.has(slug); n++) slug = `${slugifyTag(item.name)}-${n}`;
    slugs.add(slug);
    return { slug, name: item.name, description: item.description, group: item.group, count: byTag.get(item.name)!.length };
  });
  const payloads: { [slug: string]: ApiTagPayload } = {};
  const index: ApiIndexEntry[] = [];
  for (const tag of tags) {
    const operations = byTag.get(tag.name)!;
    const used = new Set(operations.flatMap(op => op.security));
    const securitySchemes: { [name: string]: ApiSecurityScheme } = {};
    [...used].sort().forEach(name => { if (schemes[name]) securitySchemes[name] = schemes[name]; });
    payloads[tag.slug] = { tag, operations, schemas: reachableSchemas(operations, schemas), securitySchemes };
    operations.forEach(op => index.push({ tag: tag.slug, operationId: op.operationId, method: op.method, path: op.path, summary: op.summary }));
  }
  return { version: String(((spec.info ?? {}) as SchemaNode).version ?? ""), index, tags, payloads };
}
