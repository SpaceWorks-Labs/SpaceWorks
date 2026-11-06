import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import { useStageAssignments } from "./api";
import type { StageScope, StageAssignment } from "./types";
import { useNow } from "./useNow";

export function stageDueState(assignment: StageAssignment, now = Date.now()) {
  if (["completed", "cancelled"].includes(assignment.state)) return assignment.state;
  if (now >= Date.parse(assignment.due_at)) return "overdue";
  return now < Date.parse(assignment.opens_at) ? "scheduled" : "open";
}
export function StageForms({ scope, onOpen }: { scope: StageScope; onOpen: (responseId: number) => void }) {
  const [page, setPage] = useState(1);
  const query = useStageAssignments(scope, page);
  const now = useNow();
  return <ListLayout header={{ eyebrow: t`Your event`, title: t`Stage forms`, subtitle: t`Complete the forms opened for your participation.` }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Forms could not be loaded.", onRetry: () => { void query.refetch(); } }}
    isEmpty={query.data?.count === 0} empty={{ message: t`You have no stage forms to complete.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5">
      <h2 className="font-semibold">{row.title}</h2><p>{stageDueState(row, now)} · {row.required ? t`Required` : t`Optional`}</p>
      <p className="text-sm text-muted">{t`Due `}<time dateTime={row.due_at}>{new Date(row.due_at).toLocaleString(formatLocale())}</time></p>
      {row.blocked_actions.length ? <p className="text-sm">{t`Required before: ${row.blocked_actions.map(value => value.replace(/_/g, " ")).join(", ")}.`}</p> : null}
      <button className="desk-button min-h-11" type="button" onClick={() => onOpen(row.response_id)}>{t`Open ${row.title}`}</button>
    </article>) }} />;
}
