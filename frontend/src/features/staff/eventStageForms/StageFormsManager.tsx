import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import type { EventScope } from "../../events/stagedForms/privateQueries";
import { useStageDefinitions } from "./api";
export function StageFormsManager({ scope, allowedActions, onCreate, onEdit, onAssignments }: { scope: EventScope; allowedActions: string[];
  onCreate: () => void; onEdit: (id: number) => void; onAssignments: () => void }) {
  const [page, setPage] = useState(1);
  const query = useStageDefinitions(scope, page);
  return <ListLayout header={{ title: "Stage forms", subtitle: "Publish follow-up forms for each part of the event.",
    primary: allowedActions.includes("stage_create") ? { label: "Create stage form", onClick: onCreate } : undefined,
    secondary: { label: "Completion and assignments", onClick: onAssignments } }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "Stage forms could not be loaded.", onRetry: () => void query.refetch() }}
    isEmpty={query.data?.count === 0} empty={{ message: "No stage forms have been configured." }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5">
      <h2 className="title-section">{row.title}</h2><p>{row.stage.replace(/_/g, " ")} · {row.state} · {row.required ? "Required" : "Optional"}</p>
      <button type="button" className="desk-button justify-self-start" onClick={() => onEdit(row.id)}>Open {row.title}</button></article>) }} />;
}
