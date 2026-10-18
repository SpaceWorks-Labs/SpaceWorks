import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import type { EventScope } from "../../events/stagedForms/privateQueries";
import { useNow } from "../../events/stagedForms/useNow";
import { stageDueState } from "../../events/stagedForms/StageForms";
import { useManagedAssignments } from "./api";
import { AssignmentActionDialog } from "./AssignmentActionDialog";
import type { AssignmentAction, ManagedAssignment } from "./types";
export function StageAssignments({ scope, onResponse }: { scope: EventScope; onResponse: (responseId: number, finance: boolean) => void }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ assignment: ManagedAssignment; action: AssignmentAction } | null>(null);
  const query = useManagedAssignments(scope, page);
  const now = useNow();
  return <ListLayout header={{ title: "Stage completion", subtitle: "Review due states and manage individual assignments." }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Assignments could not be loaded.", onRetry: () => void query.refetch() }}
    isEmpty={query.data?.count === 0} empty={{ message: "No assignments have been activated." }} pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5">
      <h2 className="title-section">{row.title}</h2><p>{row.owner_label} · {stageDueState(row, now)} · {row.required ? "Required" : "Optional"}</p>
      <p>Due <time dateTime={row.due_at}>{new Date(row.due_at).toLocaleString()}</time> · Pinned revision ID {row.pinned_form_revision_id}</p>
      <div className="flex flex-wrap gap-3">
        {row.organizer_detail_available ? <button type="button" className="desk-button" onClick={() => onResponse(row.response_id, false)}>View disclosed answers</button> : null}
        {row.finance_detail_available ? <button type="button" className="desk-button" onClick={() => onResponse(row.response_id, true)}>View finance answers</button> : null}
        {(["extend", "reopen", "cancel", "reassign"] as const).map(action => row.allowed_actions?.includes(action) ? <button type="button" key={action} className="desk-button" onClick={() => setSelected({ assignment: row, action })}>{action[0].toUpperCase()}{action.slice(1)}</button> : null)}
      </div></article>) }}
    detail={selected && !query.error ? <AssignmentActionDialog key={`${selected.assignment.id}:${selected.action}`} scope={scope} {...selected} onClose={() => setSelected(null)} /> : null} />;
}
