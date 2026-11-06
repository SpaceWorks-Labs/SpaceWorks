import { t } from "@lingui/core/macro";
import { useState } from "react";
import { DetailLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui/Field";
import { FormV2Fields } from "../../forms/FormV2Fields";
import type { EventScope } from "../../events/stagedForms/privateQueries";
import { useStaffStageResponse } from "./api";
import { StageAnswerFiles } from "./StageAnswerFiles";
export function StageResponseDetail({ scope, responseId, finance = false, revisions = [] }: {
  scope: EventScope; responseId: number; finance?: boolean; revisions?: number[];
}) {
  const [revision, setRevision] = useState<number | undefined>();
  const query = useStaffStageResponse(scope, responseId, finance, revision);
  const row = query.data;
  return <DetailLayout title={finance ? t`Finance stage answers` : t`Disclosed stage answers`}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "These answers are unavailable for your access.", onRetry: () => void query.refetch() }} main={<div className="grid gap-4">
      <Field label={t`Submitted revision`}><select className="desk-input" value={revision ?? "current"} onChange={event => setRevision(event.target.value === "current" ? undefined : Number(event.target.value))}>
        <option value="current">{t`Current submitted revision`}</option>{revisions.map(item => <option key={item} value={item}>{t`Revision ${item}`}</option>)}</select></Field>
      <p className="text-sm text-muted">{finance ? t`This separate finance view contains only authorized sensitive answers.` : t`Only answers disclosed to organizers are included. Sensitive answers are omitted.`}</p>
      {row ? <><p>{t`${row.assignment.title} · Selected revision `}{row.selected_revision ?? t`None`}{row.current_submitted_revision ? t` · Current ${row.current_submitted_revision}` : ""}</p>
        <fieldset disabled className="min-w-0"><legend className="sr-only">{t`Submitted answers`}</legend><FormV2Fields schema={{ ...row.schema, questions: row.schema.questions.filter(question => question.type !== "file").map(question => ({ ...question, profile_field_key: undefined })) }}
          value={{ answers: Object.fromEntries(row.answers.answers.map(answer => [answer.id, answer.value])), derivations: {}, save_choices: {}, saved_detail_versions: {} }} onChange={() => undefined} context="stage" /></fieldset></> : null}
      {row?.schema.questions.filter(question => question.type === "file").map(question => <section key={question.id} className="grid gap-3 rounded-2xl border border-line bg-panel p-4"><h2 className="title-section">{question.label}</h2>
        <StageAnswerFiles key={`${row.selected_revision}:${question.id}`} eventId={scope.eventId} value={row.answers.answers.find(answer => answer.id === question.id)?.value} /></section>)}
    </div>} />;
}
