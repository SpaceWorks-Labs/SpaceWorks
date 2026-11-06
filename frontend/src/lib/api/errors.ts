import { t } from "@lingui/core/macro";

export type ApiErrorBody = Record<string, unknown> & {
  detail?: unknown;
  code?: unknown;
};

/** Plain-language copy for refusals any write can hit (r2-superadmin-controls), shown wherever an API error renders. */
export const SPACE_READ_ONLY_MESSAGE = "This space is read-only: you can view and export, but nothing new can be created.";
export const SPACE_SUSPENDED_MESSAGE = "This space is paused by the platform operator. Nothing can be changed until it reopens.";
export const PLAN_LIMIT_MESSAGE = "This space has reached a limit of its hosting plan. A Space Manager can review the plan under Usage & limits.";

function friendlyMessage(status: number, body: ApiErrorBody, code?: string) {
  if (status === 423 && code === "space_read_only") return SPACE_READ_ONLY_MESSAGE;
  if (status === 423 && code === "space_suspended") return SPACE_SUSPENDED_MESSAGE;
  // DRF may wrap the code in a list when the refusal is raised as a ValidationError.
  const planCode = code ?? (Array.isArray(body.code) ? body.code[0] : undefined);
  if (planCode !== "plan_limit_reached") return "";
  const limit = Array.isArray(body.limit) ? body.limit[0] : body.limit;
  return typeof limit === "string" && limit.trim() ? `${limit.trim()} ${PLAN_LIMIT_MESSAGE}` : PLAN_LIMIT_MESSAGE;
}

/** The fallback when an error response carries no readable message. */
export function requestFailedMessage(status: number): string {
  return t`Request failed (${status})`;
}

export class StructuredApiError extends Error {
  readonly status: number;
  readonly detail?: string;
  readonly code?: string;
  readonly body: ApiErrorBody;
  /** Seconds from a `Retry-After` header (429 `ip_blocked`), when the response sent one. */
  readonly retryAfterSeconds?: number;

  constructor(status: number, body: ApiErrorBody, headers?: Headers) {
    const flattenMessages = (value: unknown): string[] => {
      if (typeof value === "string") return value.trim() ? [value.trim()] : [];
      if (Array.isArray(value)) return value.flatMap(flattenMessages);
      if (value && typeof value === "object") return Object.values(value).flatMap(flattenMessages);
      return [];
    };
    const detail = typeof body.detail === "string" ? body.detail.trim() : "";
    const code = typeof body.code === "string" ? body.code : undefined;
    super(friendlyMessage(status, body, code) || detail || Object.values(body).flatMap(flattenMessages).join(" ") || requestFailedMessage(status));
    this.name = "StructuredApiError";
    this.status = status;
    this.detail = detail || undefined;
    this.code = code;
    this.body = body;
    const retryAfter = Number(headers?.get("Retry-After") ?? Number.NaN);
    this.retryAfterSeconds = Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined;
  }
}

const SURFACE_OFF_CODES = new Set(["module_disabled", "feature_disabled", "capability_disabled"]);

/** A module or capability switched off for this space: the API answers a typed 404 (#183B),
 *  `{ detail, code: "module_disabled" | "feature_disabled", module | feature }`. Tell it
 *  apart from a plain "not found" by the code, never by the status. */
export function isSurfaceOff(error: unknown): error is StructuredApiError {
  return error instanceof StructuredApiError && SURFACE_OFF_CODES.has(error.code ?? "");
}

export function apiError(status: number, value: unknown, headers?: Headers) {
  const body = value && typeof value === "object" && !Array.isArray(value)
    ? value as ApiErrorBody
    : {};
  return new StructuredApiError(status, body, headers);
}

export function messageForStatus(status: number): string {
  if (status === 401) {
    return "Inventory client is not authorized";
  }

  if (status === 404) {
    return "Makerspace not found";
  }

  if (status >= 500) {
    return "Inventory service is unavailable";
  }

  return "Unable to load inventory";
}
