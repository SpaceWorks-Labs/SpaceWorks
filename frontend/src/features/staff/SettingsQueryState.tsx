import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { QueryContent } from "../../components/layouts/LayoutFrame";

/** Each settings editor keeps its existing query and its own retry boundary. */
export function SettingsQueryState({ query, resource, children }: {
  query: { isLoading?: boolean; isPending?: boolean; error?: unknown; refetch: () => unknown };
  resource: string;
  children?: ReactNode;
}) {
  return <QueryContent state={{
    status: query.isLoading ? "loading" : query.error ? "error" : "ready",
    error: t`Couldn't load ${resource}. Try again.`,
    onRetry: () => { void query.refetch(); },
  }}>{children}</QueryContent>;
}
