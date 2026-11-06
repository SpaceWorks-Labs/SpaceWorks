import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { FormBuilderV2 } from "../../forms/FormBuilderV2";
import type { FormSchemaV2 } from "../../forms/types";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { useUnsavedChanges } from "../../events/stagedForms/UnsavedChanges";
import { stageAdminPath, useDefinitionCommand, useStageDefinition } from "./api";
import { defaultStageSettings, StageSettingsFields } from "./StageSettingsFields";
import type { StageDefinition, StageSettings } from "./types";

export function StageFormBuilder({ scope, stageFormId, allowedActions, onCreated, onDirtyChange }: { scope: EventScope; stageFormId?: number;
  allowedActions: string[]; onCreated: (id: number) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useStageDefinition(scope, stageFormId);
  if (stageFormId && !query.data) return <p role={query.error ? "alert" : "status"}>{query.error ? commandError(query.error) : t`Loading stage form…`}</p>;
  if (query.data && Object.keys(defaultStageSettings()).some(key => !(key in query.data!))) return <p role="alert">{t`The stage settings response is incomplete. Reload after the event service is updated.`}</p>;
  return <Builder key={`${stageFormId ?? "new"}:${query.data?.version ?? 0}`} scope={scope} definition={query.data} allowedActions={allowedActions} onCreated={onCreated} onDirtyChange={onDirtyChange} />;
}
function Builder({ scope, definition, allowedActions, onCreated, onDirtyChange }: { scope: EventScope; definition?: StageDefinition;
  allowedActions: string[]; onCreated: (id: number) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const [settings, setSettings] = useState<StageSettings>(() => {
    if (!definition) return defaultStageSettings();
    const defaults = defaultStageSettings();
    return Object.fromEntries(Object.keys(defaults).map(key => [key, definition[key as keyof StageSettings]])) as StageSettings;
  });
  const [schema, setSchema] = useState<FormSchemaV2>(() => definition?.schema ?? { schema_version: 2, form_id: definition?.form_id ?? crypto.randomUUID(), revision: 1, questions: [] });
  const [dirty, setDirty] = useState(false);
  const [transition, setTransition] = useState<"publish" | "retire" | null>(null);
  const mutation = useDefinitionCommand(scope);
  useUnsavedChanges(dirty, onDirtyChange);
  const actions = definition?.allowed_actions ?? allowedActions;
  const canEdit = actions.includes(definition ? "stage_edit" : "stage_create");
  const path = `${stageAdminPath(scope)}stage-forms/${definition ? `${definition.id}/` : ""}`;
  return <FormPageLayout header={{ title: definition ? definition.title : t`Create stage form`, subtitle: t`Each publication preserves its immutable question revision.` }} state={{ status: "ready" }}
    submit={{ label: definition ? t`Save stage form` : t`Create draft stage`, pending: mutation.isPending, disabled: !canEdit || !dirty, disabledReason: "You need authoring access and unsaved changes.", onClick: () => {
      mutation.mutate({ path, method: definition ? "PATCH" : "POST", body: { expected_version: definition?.version ?? 0, settings, ...(definition ? { schema } : {}) } }, {
        onSuccess: result => { setDirty(false); if (!definition) onCreated(result.id); },
      });
    } }} form={<div className="grid gap-6"><fieldset disabled={!canEdit || mutation.isPending} className="grid min-w-0 gap-6"><legend className="sr-only">{t`Stage form editor`}</legend>
      <StageSettingsFields value={settings} onChange={next => { setSettings(next); setDirty(true); }} canBlock={actions.includes("stage_blocking_policy")} />
      {definition ? <FormBuilderV2 value={schema} context="stage" onChange={next => { setSchema(next); setDirty(true); }} /> : <p>{t`Create this stage, then add its questions before publishing.`}</p>}</fieldset>
      <p className="text-sm text-muted">{t`Submitted answers retain their original revision. Existing assignments keep their pinned questions until explicitly reassigned. Stage forms cannot ask for date of birth or age.`}</p>
      <div className="flex flex-wrap gap-3">{definition && ["publish", "retire"].map(action => actions.includes(`stage_${action}`) ? <button key={action} className="desk-button" type="button" disabled={dirty || mutation.isPending || action === "publish" && !definition.current_revision_id} onClick={() => setTransition(action as "publish" | "retire")}>{action === "publish" ? t`Publish revision` : t`Retire definition`}</button> : null)}
        <button type="button" className="desk-button" disabled={!dirty || mutation.isPending} onClick={() => { if (window.confirm(t`Discard your unsaved changes?`)) { setSettings(definition ? Object.fromEntries(Object.keys(defaultStageSettings()).map(key => [key, definition[key as keyof StageSettings]])) as StageSettings : defaultStageSettings()); setSchema(definition?.schema ?? { ...schema, questions: [] }); setDirty(false); } }}>{t`Discard changes`}</button></div>
      {dirty ? <p role="status">{t`You have unsaved changes. Save before publishing.`}</p> : mutation.isSuccess ? <p role="status">{t`Changes saved.`}</p> : null}
      {mutation.error ? <p role="alert">{commandError(mutation.error)}</p> : null}
      <ConfirmDialog open={Boolean(transition)} title={transition === "publish" ? t`Publish this revision?` : t`Retire this definition?`}
        message={transition === "publish" ? t`New eligible assignments will use these questions and timing. Existing assignments retain their pinned revision.` : t`New assignments stop. Existing assignments remain due until explicitly cancelled or reassigned.`}
        pending={mutation.isPending} onCancel={() => setTransition(null)} onConfirm={() => {
          if (definition && transition) mutation.mutate({ path: `${path}${transition}/`, body: { expected_version: definition.version } }, { onSuccess: () => setTransition(null) });
        }} /></div>} />;
}
