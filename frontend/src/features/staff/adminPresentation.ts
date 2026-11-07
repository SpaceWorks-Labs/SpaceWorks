import { t } from "@lingui/core/macro";
import type { QueryState } from "../../components/ui";

/** Screens retain query ownership; layouts own the visible loading/error state. */
export function adminQueryState(query: { isLoading: boolean; isError: boolean; refetch: () => unknown }, resource: string): QueryState {
  if (query.isLoading) return { status: "loading" };
  if (query.isError) return { status: "error", error: t`Couldn't load ${resource}. Try again.`, onRetry: () => { void query.refetch(); } };
  return { status: "ready" };
}
