import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import { usePayouts } from "./api";
import type { FinanceScope } from "./types";

export function PayoutQueue({ scope, onOpen }: { scope: FinanceScope; onOpen: (id: string) => void }) {
  const [page, setPage] = useState(1);
  const query = usePayouts(scope, page);
  return <ListLayout header={{ eyebrow: "Finance", title: "Event payouts", subtitle: "Review liabilities and record completed payments." }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Unable to load the finance queue.", onRetry: () => { void query.refetch(); } }}
    isEmpty={query.data?.count === 0} empty={{ message: "There are no event payout obligations here." }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article className="grid gap-3 rounded-2xl border border-line bg-panel p-5" key={row.id}>
      <h2 className="font-semibold">{row.event_title}</h2><p>{row.currency} {row.remaining_minor} minor units remaining · {row.state}</p>
      <p className="text-sm text-muted">Eligibility: {row.eligibility_status.replace(/_/g, " ")}</p>
      <button className="desk-button min-h-11" type="button" onClick={() => onOpen(row.id)}>Review obligation</button>
    </article>) }} />;
}
