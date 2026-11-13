import { getAccessToken } from "./client";
import { StructuredApiError } from "./errors";

/** Identity may personalize public reads, but cannot make them depend on a live session.
 * Shared with profiles, tenant reads/polls and public binary downloads. The authenticated
 * callback owns refresh-and-retry; the anonymous callback must omit Authorization.
 */
export async function withOptionalSession<T>(authenticated: () => Promise<T>, anonymous: () => Promise<T>): Promise<T> {
  if (!getAccessToken("person")) return anonymous();
  try {
    return await authenticated();
  } catch (error) {
    if (!(error instanceof StructuredApiError) || ![401, 403].includes(error.status)) throw error;
  }
  return anonymous();
}
