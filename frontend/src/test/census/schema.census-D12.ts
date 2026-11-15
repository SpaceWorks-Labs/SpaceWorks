import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { ROOT } from "./source.census-D12";
import { opaqueClientField, declaredClientPage } from "./clientShape.census-D12";
import programmeFixture from "../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json";

type Schema = {
  $ref?: string; type?: string; format?: string; nullable?: boolean; enum?: unknown[];
  default?: unknown; properties?: Record<string, Schema>; allOf?: Schema[]; required?: string[];
  oneOf?: Schema[]; anyOf?: Schema[]; minItems?: number; minLength?: number;
  minimum?: number; pattern?: string; additionalProperties?: boolean | Schema; items?: Schema;
};
type Operation = { responses?: Record<string, { content?: Record<string, { schema?: Schema }> }> };
const spec = JSON.parse(readFileSync(resolve(ROOT, "openapi-schema.json"), "utf8")) as {
  paths: Record<string, Record<string, Operation>>; components: { schemas: Record<string, Schema> };
};
const endpoints = Object.entries(spec.paths).map(([path, methods]) => ({ path, methods,
  specificity: path.replace(/\{[^}]+\}/g, "").length,
  match: new RegExp(`^${path.replace(/\/$/, "").replace(/[.*+?^$()|[\]\\]/g, "\\$&").replace(/\{[^}]+\}/g, "[^/]+")}/?$`) }))
  .sort((a, b) => b.specificity - a.specificity);
function dereference(schema: Schema, refs: string[] = []): Schema {
  if (schema.$ref) {
    if (refs.includes(schema.$ref)) throw new Error(`D12 recursive schema ${schema.$ref}`);
    const target = spec.components.schemas[schema.$ref.split("/").pop()!];
    if (!target) throw new Error(`D12 unknown schema ${schema.$ref}`);
    return dereference(target, [...refs, schema.$ref]);
  }
  if (schema.allOf) {
    const parts = schema.allOf.map(item => dereference(item, refs));
    const merged = Object.assign({}, ...parts, schema, { allOf: undefined }) as Schema;
    // OpenAPI wraps scalar enum references in allOf too. Adding properties:{}
    // to every composition turned channel/status strings into objects and
    // crashed perfectly valid consumers (DeliveryLogScreen.words, for example).
    if ([...parts, schema].some(part => part.properties)) merged.properties = Object.assign({},
      ...parts.map(part => part.properties ?? {}), schema.properties ?? {});
    const enums = [...parts, schema].flatMap(part => part.enum ? [part.enum] : []);
    if (enums.length) merged.enum = enums[0].filter(value => enums.every(values => values.includes(value)));
    if (enums.length && !merged.enum?.length) throw new Error("D12 incompatible allOf enum constraints");
    return merged;
  }
  return schema;
}
export function operationFor(path: string, method = "GET") {
  const endpoint = endpoints.find(item => item.match.test(`/api/v1${path}`));
  const operation = endpoint?.methods[method.toLowerCase()];
  if (!operation) throw new Error(`D12 missing OpenAPI operation: ${method} ${path}`);
  return { pattern: endpoint!.path, operation };
}

// Construct projections from declared response shapes, preserving required
// configuration tuples. Unsupported constraints remain explicit fixture errors.
function zeroValue(input: Schema, key: string, depth = 0, admission = false): unknown {
  if (depth > 24) throw new Error(`D12 recursive object fixture at ${key}`);
  const schema = dereference(input);
  if (schema.oneOf || schema.anyOf) {
    const variants = schema.oneOf ?? schema.anyOf!;
    if (schema.nullable || variants.some(item => item.type === "null")) return null;
    // A deterministic first declared variant is a valid JSON-schema witness, not
    // evidence that every variant has been exercised by this state census.
    return zeroValue(variants[0], key, depth + 1, admission);
  }
  if (schema.enum?.length) return admission ? ["active", "accepted", "open", "normal"].find(value => schema.enum!.includes(value)) ?? schema.enum[0] : schema.enum[0];
  if (admission && /\.(?:id|makerspace|makerspace_id|event_id|team_id|space_id)$/.test(key) && ["integer", "number"].includes(schema.type ?? "")) return 1;
  if (admission && schema.type === "boolean" && /\.(?:can_|has_)/.test(key)) return true;
  if (schema.nullable) return null;
  if (schema.type === "array") {
    if (admission) {
      if (!schema.items) throw new Error(`D12 missing admission item schema at ${key}`);
      return Array.from({ length: Math.max(1, schema.minItems ?? 0) }, () => zeroValue(schema.items!, `${key}[]`, depth + 1, true));
    }
    // Required tuples (theme colour ramps, for example) are configuration, not
    // domain collections. Their schema minimum must survive an empty response.
    return Array.from({ length: schema.minItems ?? 0 }, () => zeroValue(schema.items!, `${key}[]`, depth + 1));
  }
  if (schema.type === "object" && !Object.keys(schema.properties ?? {}).length)
    return opaqueClientField(key) ?? {};
  if (schema.properties || schema.type === "object") return Object.fromEntries(
    Object.entries(schema.properties ?? {}).map(([name, child]) => [name, zeroValue(child, `${key}.${name}`, depth + 1, admission)]));
  if (schema.type === "boolean") return schema.default ?? false;
  if (schema.type === "integer" || schema.type === "number") return Math.max(0, schema.minimum ?? 0);
  if (schema.type === "string") {
    if (schema.default !== undefined) return schema.default;
    if (schema.format === "date-time") return "2026-11-15T12:00:00Z";
    if (schema.format === "date") return "2026-11-15";
    if (schema.format === "uuid") return "11111111-1111-4111-8111-111111111111";
    if (schema.format === "email") return "d12@example.test";
    if (schema.format === "uri") return "https://example.test/d12";
    if (schema.format && !["decimal", "time"].includes(schema.format)) throw new Error(`D12 unsupported format ${key}: ${schema.format}`);
    if (schema.format === "decimal") return "0.00";
    if (schema.format === "time") return "12:00:00";
    if (schema.pattern) {
      const sample = ["", "0.00", "lab", "#006e63", "d12", "0", "G-D12"].find(value => value.length >= (schema.minLength ?? 0) && new RegExp(schema.pattern!).test(value));
      if (sample !== undefined) return sample;
      throw new Error(`D12 needs a pattern fixture for ${key}: ${schema.pattern}`);
    }
    if (admission) return /\.slug$/.test(key) ? "lab" : "D12 fixture".padEnd(schema.minLength ?? 0, "x");
    return "".padEnd(schema.minLength ?? 0, "x");
  }
  if (schema.type === "null") return null;
  // OpenAPI's {} means unconstrained JSON, for which null is a valid witness.
  // Never invent array/object fields for a client whose schema omitted them.
  if (Object.keys(schema).every(name => ["description", "title", "readOnly", "writeOnly"].includes(name))) return opaqueClientField(key) ?? null;
  throw new Error(`D12 needs an explicit response fixture for ${key}`);
}
export const EMPTY_PAGE = { count: 0, next: null, previous: null, results: [] };
export function admissionResponse(path: string) {
  const { operation } = operationFor(path);
  const schema = operation.responses?.["200"]?.content?.["application/json"]?.schema;
  if (!schema) throw new Error(`D12 needs a JSON admission contract for ${path}`);
  if (dereference(schema).type === "array" && declaredClientPage(path)) return EMPTY_PAGE;
  return zeroValue(schema, path, 0, true);
}
// Reads keyed by a public identifier whose suffix names a view of that one record.
// The serializers need a real row, so the only "nothing here" answer is the same
// enumeration-safe 404 as a trailing-identifier read; an all-zero record is not a wire value.
const IDENTITY_READS = [
  /^\/public\/event-certificates\/[^/]+\/verify\/?$/, // certificates VerificationSerializer
  /^\/public\/machine-service\/requests\/[^/]+\/status\/?$/, // bearer job-status token
  /^\/public\/[^/]+\/events\/[^/]+\/feedback\/?$/, // closed/missing/not-ended survey
  /^\/public\/organizations\/[^/]+\/page\/?$/, // unpublished organization page (publicOrMissing)
  /^\/member\/machines\/\d+\/session\/?$/, // one machine's session preview
];
export function emptyResponse(path: string, method = "GET"): { status: number; body: unknown } {
  const { pattern, operation } = operationFor(path, method);
  const status = Number(Object.keys(operation.responses ?? {}).find(code => /^2\d\d$/.test(code)));
  const raw = operation.responses?.[String(status)]?.content?.["application/json"]?.schema;
  if (!raw) throw new Error(`D12 needs a JSON success contract for ${path}`);
  const schema = dereference(raw);
  if (method === "GET" && /^\/public\/event-programmes\/[^/]+\/context$/.test(path)) {
    // A context is a validated projection, not a missing resource or an all-zero
    // serializer. Ineligible accounts receive no advertised admission commands.
    const body = structuredClone(programmeFixture.context);
    body.eligibility = { eligible: false, reason: null };
    for (const name of Object.keys(body.routes)) if (!["context", "member_base"].includes(name))
      (body.routes as Record<string, unknown>)[name] = null;
    return { status, body };
  }
  // A platform override may deliberately be blank (legal_pages.py:44-46,
  // set_platform_page accepts blank); this is a projection, not a missing slug.
  if (schema.properties?.markdown && path.startsWith("/discover/legal/")) return {
    status, body: { ...zeroValue(schema, path) as object, slug: path.split("/").pop(), source: "platform", markdown: "" },
  };
  // Decision 576: fixtures follow the actual wire contract. DRF ListAPIView
  // and member_card_admin_views.py:84 return pages despite many=True response
  // annotations. CENSUS-D12-57 separately pins that OpenAPI documentation defect.
  if (schema.type === "array") return { status, body: method === "GET" && declaredClientPage(path)
    ? EMPTY_PAGE : zeroValue(schema, path) };
  if (schema.properties?.results && Object.keys(schema.properties).sort().join(",") === "count,next,previous,results")
    return { status, body: EMPTY_PAGE };
  // Resource absence is distinct from an empty summary/settings projection.
  if (method === "GET" && (/\/\{[^}]+\}\/?$/.test(pattern) || IDENTITY_READS.some(read => read.test(path))) && !schema.properties?.markdown) return {
    status: 404, body: { code: "not_found", detail: "Census record not found." },
  };
  return { status, body: zeroValue(schema, path) };
}
