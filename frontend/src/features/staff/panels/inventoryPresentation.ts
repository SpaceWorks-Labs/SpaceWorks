import { t } from "@lingui/core/macro";
import type { QueryState } from "../../../components/ui";

// Keep query ownership in the screen; layouts only choose its presentation.
export function inventoryQueryState(query: { isLoading: boolean; error: unknown; refetch: () => unknown }, resource: string): QueryState {
  return query.isLoading ? { status: "loading" } : query.error
    ? { status: "error", error: t`Couldn't load ${resource}. Try again.`, onRetry: () => { void query.refetch(); } }
    : { status: "ready" };
}
