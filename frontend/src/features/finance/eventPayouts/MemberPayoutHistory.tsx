import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import { useMemberPayoutHistory } from "./api";

export function MemberPayoutHistory({ actorId, onOpen }: { actorId: number; onOpen: (id: string) => void }) {
  const [page, setPage] = useState(1);
  const query = useMemberPayoutHistory(actorId, page);
  return <ListLayout header={{ title: "Your reimbursements", subtitle: "Approved amounts and recorded payouts." }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Payout history could not be loaded.", onRetry: () => { void query.refetch(); } }}
    isEmpty={query.data?.count === 0} empty={{ message: "You have no approved reimbursements yet." }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5">
      <h2 className="font-semibold">{row.event_title}</h2><p>{row.state} · {row.currency} {row.approved_minor} minor units approved</p>
      <p>{row.effective_paid_minor} minor units recorded paid · {row.remaining_minor} remaining</p>
      <button type="button" className="desk-button min-h-11" onClick={() => onOpen(row.id)}>View reimbursement</button>
    </article>) }} />;
}
