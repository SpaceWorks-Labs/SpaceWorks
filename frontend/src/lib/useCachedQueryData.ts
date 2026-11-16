import { hashKey, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore } from "react";

/**
 * Read another component's cached query data without becoming its observer.
 *
 * A disabled `useQuery({ queryFn: skipToken })` subscriber writes its options onto the
 * shared query, so a later invalidation refetches with `skipToken` and fails ("Missing
 * queryFn"). This hook only listens to the cache: it never fetches, never makes the
 * query active and never replaces the owner's queryFn.
 */
export function useCachedQueryData<T>(queryKey: QueryKey): T | undefined {
  const client = useQueryClient();
  const hash = hashKey(queryKey);
  const subscribe = useCallback((notify: () => void) => client.getQueryCache().subscribe(event => {
    if (event.query.queryHash === hash) notify();
  }), [client, hash]);
  return useSyncExternalStore(subscribe, () => client.getQueryData<T>(queryKey));
}
