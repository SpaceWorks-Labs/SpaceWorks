import { t } from "@lingui/core/macro";
import { useState } from "react";

import { EmptyState, ErrorBlock, ListRow, Pagination, RelativeTime, Skeleton } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { useCrossLink } from "../crossLinks/staffHref";
import { AttributionLine } from "./InventoryPanelParts";
import type { LendingHistoryResponse } from "./InventoryPanelShared";
import { useStaffGet } from "./shared";

const PAGE_SIZE = 10;

/**
 * IN5: every lend of one item, newest first, paged by the server's `limit`/`offset`. Each row
 * opens the loan in Requests; the borrower's other loans are one click further (ledger search).
 */
export function LendingHistory({ productId }: { productId: number }) {
  const [page, setPage] = useState(1);
  const link = useCrossLink();
  const history = useStaffGet<LendingHistoryResponse>(["lending-history", productId, page],
    `/admin/inventory/${productId}/lending-history?limit=${PAGE_SIZE}&offset=${(page - 1) * PAGE_SIZE}`);
  const last = history.data?.last_borrower;
  const recent = history.data?.recent ?? [];
  const count = history.data?.count ?? recent.length;
  return <section className="grid gap-4"><h3 className="title-section">{t`Loan history`}</h3>
    {history.isLoading ? <Skeleton className="h-40" /> : history.error ? <ErrorBlock error={history.error} resource={t`loan history`} onRetry={() => { void history.refetch(); }} /> : !recent.length ? <EmptyState message={t`No loan history yet. Handovers will appear here.`} /> : null}
    {last && page === 1 ? <p className="text-sm">{t`Last borrower: ${last.username} · `}<RelativeTime date={last.issued_at} exact /><AttributionLine acceptedBy={last.accepted_by} issuedBy={last.issued_by} /></p> : null}
    {recent.map(entry => {
      const borrower = link("ledger", { q: entry.username });
      return <ListRow key={entry.id} title={entry.username} identity={{ kind: "avatar", name: entry.username, seed: entry.username }}
        href={entry.request_id ? link("requests", { id: entry.request_id }) : undefined}
        meta={<><RelativeTime date={entry.issued_at} exact /><AttributionLine acceptedBy={entry.accepted_by} issuedBy={entry.issued_by} /></>}
        right={<span className="flex flex-wrap items-center gap-3"><span className="tabular-nums">{t`${entry.quantity} units`}</span>
          {borrower ? <RouteLink className="text-sm font-semibold underline" href={borrower}>{t`What they have out`}</RouteLink> : null}</span>} />;
    })}
    {count > PAGE_SIZE ? <Pagination page={page} totalPages={Math.ceil(count / PAGE_SIZE)} onChange={setPage} /> : null}
  </section>;
}
