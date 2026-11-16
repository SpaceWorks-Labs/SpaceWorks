import {
  API_V1_URL,
  cacheTenantPublishableKey,
  getTenantPublishableKey,
  publicHeaders,
  staffFetch,
} from "./client";
import { apiError } from "./errors";
import { withOptionalSession } from "./optionalSession";
import { memberRequest, publicAnonymousRequest, publicV1Request } from "./requests";
import type { TenantBootstrap } from "./types";

/** Discovery may cache a tenant's key without changing the current page's ambient tenant. */
export async function bootstrapTenant(params: { tenant?: string; slug?: string }, { activate = true } = {}) {
  const search = new URLSearchParams();
  if (params.tenant) search.set("tenant", params.tenant);
  if (params.slug) search.set("slug", params.slug);
  const bootstrap = await publicAnonymousRequest<TenantBootstrap>(`/bootstrap?${search.toString()}`);
  cacheTenantPublishableKey(
    bootstrap.makerspace.slug,
    bootstrap.public_api.publishable_key,
    activate,
  );
  return bootstrap;
}

async function tenantPublishableKey(slug: string): Promise<string> {
  const normalized = slug.trim();
  let publishableKey = getTenantPublishableKey(normalized);
  if (!publishableKey) {
    const bootstrap = await bootstrapTenant({ slug: normalized });
    publishableKey = bootstrap.public_api.publishable_key;
  }
  return publishableKey;
}

export async function tenantPublicRequest<T>(
  slug: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
  return publicV1Request<T>(path, options, await tenantPublishableKey(slug));
}

/** Keep the tenant credential explicit while reusing authenticated refresh-and-retry. */
export async function tenantMemberRequest<T>(
  slug: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = await publicHeaders(await tenantPublishableKey(slug));
  return memberRequest<T>(path, {
    ...options,
    headers: { ...headers, ...(options.headers ?? {}) },
  });
}

export async function tenantPublicRequestBlob(slug: string, path: string): Promise<Blob> {
  const headers = await publicHeaders(await tenantPublishableKey(slug));
  const blob = async (response: Response) => {
    if (!response.ok) throw apiError(response.status, await response.json().catch(() => ({})));
    return response.blob();
  };
  return withOptionalSession(
    async () => blob(await staffFetch(path, { headers }, true, "person")),
    async () => blob(await fetch(`${API_V1_URL}${path}`, { headers })),
  );
}
