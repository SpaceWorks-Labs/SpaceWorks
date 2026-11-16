import { ErrorBlock } from "./ErrorBlock";

type FailedQuery = { error: unknown; refetch: () => unknown };

/** Keep independent read failures recoverable even when another widget replaces its body. */
export function QueryErrors({ queries }: { queries: readonly FailedQuery[] }) {
  return <>{queries.map((query, index) => query.error
    ? <ErrorBlock key={index} error={query.error} onRetry={() => { void query.refetch(); }} />
    : null)}</>;
}
