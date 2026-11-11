import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListLayout } from "../../../components/layouts";
import type { EventScope } from "../../events/stagedForms/privateQueries";
import { useStageDefinitions } from "./api";
import { stageDefinitionStateLabel, stageNameLabel } from "../../events/stagedForms/labels";
export function StageFormsManager({ scope, allowedActions, onCreate, onEdit, onAssignments }: { scope: EventScope; allowedActions: string[];
  onCreate: () => void; onEdit: (id: number) => void; onAssignments: () => void }) {
  const [page, setPage] = useState(1);
  const query = useStageDefinitions(scope, page);
  return <ListLayout header={{ title: t`Stage forms`, subtitle: t`Publish follow-up forms for each part of the event.`,
    primary: allowedActions.includes("stage_create") ? { label: t`Create stage form`, onClick: onCreate } : undefined,
    secondary: { label: t`Completion and assignments`, onClick: onAssignments } }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: t`Stage forms could not be loaded.`, onRetry: () => void query.refetch() }}
    isEmpty={query.data?.count === 0} empty={{ message: t`No stage forms have been configured.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: "rows", rows: query.data?.results.map(row => <article key={row.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-5">
      <h2 className="title-section">{row.title}</h2><p>{stageNameLabel(row.stage)} · {stageDefinitionStateLabel(row.state)} · {row.required ? t`Required` : t`Optional`}</p>
      <button type="button" className="desk-button justify-self-start" onClick={() => onEdit(row.id)}>{t`Open ${row.title}`}</button></article>) }} />;
}
