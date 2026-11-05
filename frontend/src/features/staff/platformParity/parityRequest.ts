import { staffRequest } from "../../../lib/api";
import { StructuredApiError } from "../../../lib/api/errors";

// Hand-written request helpers and types, like the other platform panels (#190 console parity).
export { PAGE_SIZE, post, type Page } from "../platformSpaces/spacesApi";

export function patch<T>(path: string, body: unknown) {
  return staffRequest<T>(path, { method: "PATCH", body: JSON.stringify(body) }, "platform");
}

export function remove(path: string) {
  return staffRequest<void>(path, { method: "DELETE" }, "platform");
}

/** The first message DRF attached to one field of a 400, so a form can show it under that field. */
export function fieldError(error: unknown, field: string): string | undefined {
  if (!(error instanceof StructuredApiError) || error.status !== 400) return undefined;
  const value = error.body[field];
  const first = Array.isArray(value) ? value[0] : value;
  return typeof first === "string" ? first : undefined;
}

/** Turn a `datetime-local` value into ISO, or null when it is empty or unreadable. */
export function isoOrNull(local: string) {
  if (!local) return null;
  const date = new Date(local);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
