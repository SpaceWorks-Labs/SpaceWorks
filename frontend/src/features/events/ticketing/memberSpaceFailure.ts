import { isRetryable } from "../../../lib/api/errors";

/**
 * A scoped member route whose space failed to load is an error state, never the contextless
 * "unavailable here" notice. Decision 588: Retry only for an outage; a refusal keeps its explanation.
 * Only a space with NO cached bootstrap (no `makerspaceId`) replaces the page: a failed background
 * refetch over cached data keeps the working page.
 */
export function memberSpaceFailure(space: { makerspaceId: number; error?: Error | null; refetch?: () => unknown }) {
  return space.error && !space.makerspaceId ? { status: "error" as const, error: space.error.message,
    onRetry: isRetryable(space.error) && space.refetch ? () => { void space.refetch?.(); } : undefined } : undefined;
}
