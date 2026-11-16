import { t } from "@lingui/core/macro";
import type { QueryState } from "../../../components/ui";
import { isRetryable } from "../../../lib/api/errors";

// Keep query ownership in the screen; layouts only choose its presentation.
export function inventoryQueryState(query: { isLoading: boolean; error: unknown; refetch: () => unknown }, resource: string): QueryState {
  return query.isLoading ? { status: "loading" } : query.error
    ? { status: "error", error: isRetryable(query.error) ? t`Couldn't load ${resource}. Try again.` : query.error instanceof Error ? query.error.message : t`This content is no longer available for your access.`, onRetry: isRetryable(query.error) ? () => { void query.refetch(); } : undefined }
    : { status: "ready" };
}
