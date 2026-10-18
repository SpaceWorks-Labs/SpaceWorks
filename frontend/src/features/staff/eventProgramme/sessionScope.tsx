import { Fragment, useEffect, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getAccessToken, StructuredApiError } from "../../../lib/api";
import { currentSessionContext } from "../../../lib/api/sessionContext";
import { browserSessionIdentity } from "../../../lib/api/reauthentication";
export function sessionScope() {
  const context = currentSessionContext();
  return [context, browserSessionIdentity(getAccessToken(context))] as const;
}
/** G mounts this at protected route/drawer boundaries so auth changes discard drafts and object URLs. */
export function isProtectedDenial(error: unknown) { return error instanceof StructuredApiError && [401, 403, 404].includes(error.status); }
/** A failed authorization refresh must not leave old rows available on the next mount. */
export function useClearDeniedQuery(error: unknown, key: readonly unknown[]) {
  const client = useQueryClient();
  const denied = isProtectedDenial(error);
  const encodedKey = JSON.stringify(key);
  useEffect(() => {
    if (!denied) return;
    const query = client.getQueryCache().find({ queryKey: JSON.parse(encodedKey), exact: true });
    if (query?.state.data !== undefined) query.setState({ data: undefined });
  }, [client, denied, encodedKey]);
  return denied;
}
export function ProgrammeSessionBoundary({ children, error }: { children: ReactNode; error?: unknown }) {
  if (isProtectedDenial(error)) return <p role="alert" className="text-sm text-danger">This content is no longer available for your access.</p>;
  return <Fragment key={JSON.stringify(sessionScope())}>{children}</Fragment>;
}
