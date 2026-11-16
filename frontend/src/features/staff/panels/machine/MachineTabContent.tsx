import type { ReactNode } from "react";
import { QueryContent } from "../../../../components/layouts/LayoutFrame";
import { opsQueryState } from "../../opsPresentation";

/** A drawer tab keeps its form available while its existing list query changes state. */
export function MachineTabContent({ query, resource, empty, message, children }: {
  query: { isLoading: boolean; error: unknown; refetch: () => unknown };
  resource: string; empty: boolean; message: string; children: ReactNode;
}) {
  return <QueryContent state={opsQueryState(query, resource)} isEmpty={empty} empty={{ message }}>{children}</QueryContent>;
}
