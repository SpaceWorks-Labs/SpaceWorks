import { t } from "@lingui/core/macro";
import type { QueryState } from "../../components/ui";
import { isRetryable } from "../../lib/api/errors";

/** Screens retain query ownership; layouts own the visible loading/error state. */
export function adminQueryState(query: { isLoading: boolean; isError: boolean; error?: unknown; refetch: () => unknown }, resource: string): QueryState {
  if (query.isLoading) return { status: "loading" };
  // Decision 588: only an outage says "Try again" and offers Retry; a refusal shows its own explanation.
  if (query.isError) return isRetryable(query.error)
    ? { status: "error", error: t`Couldn't load ${resource}. Try again.`, onRetry: () => { void query.refetch(); } }
    : { status: "error", error: query.error instanceof Error ? query.error.message : t`You can't open ${resource} here.` };
  return { status: "ready" };
}
