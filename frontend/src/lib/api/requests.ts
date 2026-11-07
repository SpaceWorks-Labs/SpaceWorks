import { t } from "@lingui/core/macro";
import { currentSessionContext, type SessionContext } from "./sessionContext";
import { API_URL, API_V1_URL, authHeaders, publicHeaders, staffFetch } from "./client";
import { apiError, messageForStatus } from "./errors";
import { withOptionalSession } from "./optionalSession";
import type { StaffAuthUser } from "./types";

export async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: await publicHeaders(),
  });

  if (!response.ok) {
    throw new Error(`${messageForStatus(response.status)} (${response.status})`);
  }

  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return fetchJson<T>(`${API_URL}${path}`);
}

export async function publicV1Request<T>(
  path: string,
  options: RequestInit = {},
  publishableKey?: string,
): Promise<T> {
  if ((options.method ?? "GET").toUpperCase() === "GET") {
    const headers = { ...(await publicHeaders(publishableKey)), ...(options.headers ?? {}) };
    return withOptionalSession(
      () => memberRequest<T>(path, { ...options, headers }),
      () => publicV1Json<T>(path, { ...options, headers: { ...headers, Authorization: "" } }, publishableKey),
    );
  }
  // Mutations keep their existing auth requirements and are never retried anonymously.
  return publicV1Json<T>(path, options, publishableKey);
}

/** Anonymous public GET for reads that never depend on identity (the tenant bootstrap).
 * Sending a member's bearer there only earns a staff-route 403 and an anonymous retry. */
export async function publicAnonymousRequest<T>(path: string, publishableKey?: string): Promise<T> {
  return publicV1Json<T>(path, { headers: { Authorization: "" } }, publishableKey);
}

async function publicV1Json<T>(path: string, options: RequestInit, publishableKey?: string): Promise<T> {
  const response = await fetch(`${API_V1_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(await publicHeaders(publishableKey)),
      ...authHeaders("person"),
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw apiError(response.status, await response.json().catch(() => ({})), response.headers);
  }

  return (await response.json()) as T;
}

export async function fetchMe(context = currentSessionContext()): Promise<StaffAuthUser> {
  return staffRequest<StaffAuthUser>("/auth/me", {}, context);
}

/** Fetch a binary/non-JSON authenticated resource as a Blob.
 *
 * `<img src>` cannot carry an Authorization header, so an authenticated image has to be
 * fetched and handed to the DOM as an object URL. Callers must revoke that URL.
 */
export async function staffRequestBlob(
  path: string,
  options: RequestInit = {},
): Promise<Blob> {
  const response = await staffFetch(path, options);
  if (!response.ok) {
    throw apiError(response.status, await response.json().catch(() => ({})), response.headers);
  }
  return await response.blob();
}

type StaffWriteGuard = (path: string, method: string) => boolean;
let staffWriteGuard: StaffWriteGuard | null = null;

/** #195: the superadmin console asks before writing in a paused or read-only space (null clears). */
export function setStaffWriteGuard(guard: StaffWriteGuard | null) {
  staffWriteGuard = guard;
}

export async function staffRequest<T>(
  path: string,
  options: RequestInit = {},
  context: SessionContext = currentSessionContext(),
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  if (staffWriteGuard && !["GET", "HEAD", "OPTIONS"].includes(method) && !staffWriteGuard(path, method)) {
    throw apiError(409, { detail: t`Cancelled. Nothing was changed.`, code: "superadmin_write_cancelled" });
  }
  const response = await staffFetch(path, options, false, context);

  if (!response.ok) {
    throw apiError(response.status, await response.json().catch(() => ({})), response.headers);
  }
  // 204 No Content (e.g. DRF destroy) has an empty body - parsing it as JSON
  // would throw and surface a successful mutation as a failure.
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function memberRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await staffFetch(path, options, true, "person");
  if (!response.ok) {
    throw apiError(response.status, await response.json().catch(() => ({})), response.headers);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function memberRequestBlob(path: string): Promise<Blob> {
  const response = await staffFetch(path, {}, true, "person");
  if (!response.ok) throw apiError(response.status, await response.json().catch(() => ({})), response.headers);
  return response.blob();
}

export async function downloadStaffFile(path: string, filename: string) {
  const response = await fetch(`${API_V1_URL}${path}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error(t`Download failed (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
