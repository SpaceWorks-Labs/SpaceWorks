import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import { useMemberPayoutHistory } from "./api";
import { money, scopeIdentity } from "./format";
import { permits } from "./types";

export function MemberPayoutHistory(props: { actorId: number; onOpen: (id: string) => void }) {
  return <HistoryContent key={scopeIdentity(props.actorId)} {...props} />;
}
function HistoryContent({ actorId, onOpen }: { actorId: number; onOpen: (id: string) => void }) {
  const [page, setPage] = useState(1);
  const query = useMemberPayoutHistory(actorId, page);
  return <ListLayout header={{ title: t`Your reimbursements`, subtitle: t`Approved amounts and recorded payouts.` }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Payout history could not be loaded.", onRetry: () => { void query.refetch(); } }}
    isEmpty={query.data?.count === 0} empty={{ message: t`You have no approved reimbursements yet.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5">
      <h2 className="font-semibold">{row.event_title}</h2><p>{row.state} · {money(row.approved_minor, row.currency)} approved</p>
      <p>{t`${money(row.effective_paid_minor, row.currency)} recorded paid · ${money(row.remaining_minor, row.currency)} remaining`}</p>
      {permits(row, "view") ? <button type="button" className="desk-button min-h-11" onClick={() => onOpen(row.id)}>{t`View reimbursement`}</button> : null}
    </article>) }} />;
}
