import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import type { EventScope } from "../../events/stagedForms/privateQueries";
import { useClaimQueue } from "./api";
export function ReimbursementClaims({ scope, onOpen }: { scope: EventScope; onOpen: (id: number) => void }) {
  const [page, setPage] = useState(1);
  const query = useClaimQueue(scope, page);
  return <ListLayout header={{ title: t`Expense claims`, subtitle: t`Screen claims or open the authorized finance decision view.` }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Claims could not be loaded.", onRetry: () => void query.refetch() }}
    isEmpty={query.data?.count === 0} empty={{ message: t`No claims to review.` }} pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">{row.owner_label}</h2>
      <p>{t`${row.state.replace(/_/g, " ")} · ${row.claimed_minor} minor units (${row.currency})`}</p><p>{t`Due ${new Date(row.due_at).toLocaleString(formatLocale())}`}</p>
      <button type="button" className="desk-button justify-self-start" onClick={() => onOpen(row.id)}>{t`Review claim`}</button></article>) }} />;
}
