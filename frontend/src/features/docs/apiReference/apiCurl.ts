import type { ApiOperation } from "./apiReferenceModel";
import { sampleValue, type Schemas } from "./apiSchema";

const BEARER = ["jwtAuth", "personalAccessToken", "oauth2"];
const quote = (value: string) => `'${value.replace(/'/g, "'\\''")}'`;

/**
 * A copy-ready curl call: path parameters as <placeholders>, required query and header parameters,
 * the auth header the operation accepts, and a JSON body skeleton built from the request schema.
 */
export function buildCurl(operation: ApiOperation, schemas: Schemas, origin: string) {
  const path = operation.path.replace(/\{([^}]+)\}/g, "<$1>");
  const query = operation.parameters.filter(param => param.in === "query" && param.required)
    .map(param => `${encodeURIComponent(param.name)}=<${param.name}>`);
  const url = `${origin.replace(/\/+$/, "")}${path}${query.length ? `?${query.join("&")}` : ""}`;
  const lines = [`curl -X ${operation.method} ${quote(url)}`];
  if (!operation.anonymous) {
    if (operation.security.some(name => BEARER.includes(name))) lines.push(`-H ${quote("Authorization: Bearer $SPACEWORKS_TOKEN")}`);
    else if (operation.security.includes("PublishableKey")) lines.push(`-H ${quote("X-Publishable-Key: $SPACEWORKS_PUBLISHABLE_KEY")}`);
  }
  operation.parameters.filter(param => param.in === "header" && param.required)
    .forEach(param => lines.push(`-H ${quote(`${param.name}: <${param.name}>`)}`));
  const content = operation.requestBody?.content ?? {};
  const json = Object.keys(content).find(type => type.includes("json"));
  const multipart = Object.keys(content).find(type => type.startsWith("multipart/"));
  if (json && content[json]) {
    lines.push(`-H ${quote("Content-Type: application/json")}`);
    lines.push(`-d ${quote(JSON.stringify(sampleValue(content[json]!, schemas), null, 2))}`);
  } else if (multipart && content[multipart]) {
    const body = sampleValue(content[multipart]!, schemas);
    Object.entries(body && typeof body === "object" ? body : {})
      .forEach(([name, value]) => lines.push(`-F ${quote(`${name}=${typeof value === "string" ? value : JSON.stringify(value)}`)}`));
  }
  return lines.join(" \\\n  ");
}
