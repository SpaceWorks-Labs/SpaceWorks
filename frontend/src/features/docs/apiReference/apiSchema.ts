import { refName, type SchemaNode } from "./apiReferenceModel";

export type Schemas = { [name: string]: SchemaNode };
export type SchemaField = { name: string; schema: SchemaNode; required: boolean };

const asNode = (value: unknown) => (value && typeof value === "object" && !Array.isArray(value) ? value as SchemaNode : null);
const nodes = (value: unknown) => (Array.isArray(value) ? value.map(asNode).filter((item): item is SchemaNode => Boolean(item)) : []);

/** Follow a $ref (and a lone allOf wrapper around one) to the schema it names; `name` is the last ref seen. */
export function resolveSchema(schema: SchemaNode, schemas: Schemas): { schema: SchemaNode; name: string | null } {
  let current = schema;
  let name: string | null = null;
  for (let hops = 0; hops < 16; hops++) {
    const ref = refName(current.$ref);
    const single = nodes(current.allOf);
    if (ref && schemas[ref]) { name = ref; current = schemas[ref]; continue; }
    if (single.length === 1 && !current.properties) { current = { ...current, ...single[0], allOf: undefined }; continue; }
    break;
  }
  return { schema: current, name };
}

function typeOf(schema: SchemaNode): string[] {
  if (Array.isArray(schema.type)) return schema.type.map(String);
  return typeof schema.type === "string" ? [schema.type] : [];
}

export function isNullable(schema: SchemaNode) {
  return schema.nullable === true || typeOf(schema).includes("null");
}

/** A short type label: `PublicCategory`, `string (date-time)`, `PublicCategory[]`, `A | B`. */
export function typeLabel(schema: SchemaNode, schemas: Schemas, depth = 0): string {
  if (depth > 4) return "…";
  const ref = refName(schema.$ref);
  if (ref) return ref;
  const variants = nodes(schema.oneOf).length ? nodes(schema.oneOf) : nodes(schema.anyOf);
  if (variants.length) return variants.map(item => typeLabel(item, schemas, depth + 1)).join(" | ");
  const all = nodes(schema.allOf);
  if (all.length === 1) return typeLabel(all[0], schemas, depth + 1);
  if (all.length) return all.map(item => typeLabel(item, schemas, depth + 1)).join(" & ");
  const types = typeOf(schema).filter(type => type !== "null");
  if (types.includes("array")) {
    const items = asNode(schema.items);
    return items ? `${typeLabel(items, schemas, depth + 1)}[]` : "array";
  }
  const base = types.join(" | ") || (schema.properties ? "object" : "any");
  return typeof schema.format === "string" ? `${base} (${schema.format})` : base;
}

/** Properties of an object schema, merging allOf parts; required ones first. */
export function objectFields(schema: SchemaNode, schemas: Schemas): SchemaField[] {
  const parts = [schema, ...nodes(schema.allOf).map(part => resolveSchema(part, schemas).schema)];
  const fields = new Map<string, SchemaField>();
  const required = new Set(parts.flatMap(part => (Array.isArray(part.required) ? part.required.map(String) : [])));
  for (const part of parts) {
    for (const [name, child] of Object.entries(asNode(part.properties) ?? {})) {
      const node = asNode(child);
      if (node) fields.set(name, { name, schema: node, required: required.has(name) });
    }
  }
  return [...fields.values()].sort((a, b) => Number(b.required) - Number(a.required));
}

export function variantsOf(schema: SchemaNode) {
  return nodes(schema.oneOf).length ? nodes(schema.oneOf) : nodes(schema.anyOf);
}

/** What a tree node opens onto: the object behind it, an array's items, or a union's variants. */
export function childrenOf(schema: SchemaNode, schemas: Schemas): { fields: SchemaField[]; variants: SchemaNode[]; items: SchemaNode | null } {
  const { schema: resolved } = resolveSchema(schema, schemas);
  const items = typeOf(resolved).includes("array") ? asNode(resolved.items) : null;
  return { fields: objectFields(resolved, schemas), variants: variantsOf(resolved), items };
}

export function isExpandable(schema: SchemaNode, schemas: Schemas, depth = 0): boolean {
  if (depth > 3) return false;
  const { fields, variants, items } = childrenOf(schema, schemas);
  return fields.length > 0 || variants.length > 0 || (items ? isExpandable(items, schemas, depth + 1) : false);
}

export function enumValues(schema: SchemaNode, schemas: Schemas) {
  const values = resolveSchema(schema, schemas).schema.enum;
  return Array.isArray(values) ? values.filter(value => value !== null).map(String) : [];
}

/** A small JSON skeleton for a curl body: examples where given, otherwise typed placeholders. */
export function sampleValue(schema: SchemaNode, schemas: Schemas, depth = 0, seen: Set<string> = new Set()): unknown {
  const { schema: resolved, name } = resolveSchema(schema, schemas);
  if (resolved.example !== undefined) return resolved.example;
  if (name && seen.has(name)) return {};
  const nextSeen = name ? new Set(seen).add(name) : seen;
  const values = enumValues(resolved, schemas);
  if (values.length) return values[0];
  const variants = variantsOf(resolved);
  if (variants.length) return sampleValue(variants[0], schemas, depth, nextSeen);
  const types = typeOf(resolved);
  if (types.includes("array")) {
    const items = asNode(resolved.items);
    return items && depth < 3 ? [sampleValue(items, schemas, depth + 1, nextSeen)] : [];
  }
  const fields = objectFields(resolved, schemas).filter(field => !field.schema.readOnly);
  if (fields.length || types.includes("object")) {
    if (depth >= 3) return {};
    const required = fields.filter(field => field.required);
    return Object.fromEntries((required.length ? required : fields.slice(0, 3))
      .map(field => [field.name, sampleValue(field.schema, schemas, depth + 1, nextSeen)]));
  }
  if (types.includes("integer") || types.includes("number")) return 0;
  if (types.includes("boolean")) return false;
  return resolved.format === "binary" ? "@file" : "string";
}
