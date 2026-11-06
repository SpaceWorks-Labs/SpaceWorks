import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import { usePayouts } from "./api";
import { money, scopeIdentity } from "./format";
import { MaskedPayoutExport } from "./MaskedPayoutExport";
import { permits } from "./types";
import type { FinanceScope } from "./types";

export function PayoutQueue(props: { scope: FinanceScope; onOpen: (id: string) => void }) {
  return <QueueContent key={scopeIdentity(props.scope.actorId, props.scope.makerspaceId)} {...props} />;
}
function QueueContent({ scope, onOpen }: { scope: FinanceScope; onOpen: (id: string) => void }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const query = usePayouts(scope, page);
  // Selection is restricted to the currently loaded page and current server actions.
  const ids = selected.filter(id => query.data?.results.some(row => row.id === id && permits(row, "export")));
  return <ListLayout header={{ eyebrow: t`Finance`, title: t`Event payouts`, subtitle: t`Review liabilities and record completed payments.` }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: t`Unable to load the finance queue.`, onRetry: () => { void query.refetch(); } }}
    isEmpty={query.data?.count === 0} empty={{ message: t`There are no event payout obligations here.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: value => { setPage(value); setSelected([]); } }}
    body={{ kind: "rows", rows: [
      ...(query.data?.results.map(row => <article className="grid gap-3 rounded-2xl border border-line bg-panel p-5" key={row.id}>
        <h2 className="font-semibold">{row.event_title}</h2><p>{t`${money(row.remaining_minor, row.currency)} remaining · ${row.state}`}</p>
        <p className="text-sm text-muted">{t`Eligibility: ${row.eligibility_status.replace(/_/g, " ")}`}</p>
        {permits(row, "export") ? <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={ids.includes(row.id)}
          onChange={event => setSelected(event.target.checked ? [...ids, row.id] : ids.filter(id => id !== row.id))} />{t`Select ${row.event_title} for masked CSV`}</label> : null}
        {permits(row, "view") ? <button className="desk-button min-h-11" type="button" onClick={() => onOpen(row.id)}>{t`Review obligation`}</button> : null}
      </article>) ?? []),
      <MaskedPayoutExport key={`export:${ids.map(id => query.data?.results.find(row => row.id === id)?.version).join()}`}
        scope={scope} ids={ids} allowed={ids.length > 0} />,
    ] }} />;
}
