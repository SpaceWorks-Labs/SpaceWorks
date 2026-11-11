// Publishing a badge goes through the same design approval flow as every card design: publish, or submit
// for approval when the event, organisation or space asks for it. Autosave only keeps a draft.
import { t } from "@lingui/core/macro";

import type { CardDesign } from "../../../components/card-designer/cardTypes";
import { useApproveDesign, usePublishDesign, useSubmitDesign } from "../../../components/card-designer/designerApi";

export function BadgePublish({ design, canEdit, flush, blocked }: { design: CardDesign; canEdit: boolean;
  flush: () => Promise<void>; blocked: boolean }) {
  const publish = usePublishDesign(design.id);
  const submit = useSubmitDesign(design.id);
  const approve = useApproveDesign(design.id);
  const busy = publish.isPending || submit.isPending || approve.isPending;
  const failure = [publish, submit, approve].find((mutation) => mutation.isError)?.error;
  const pending = design.pending_approval;
  const run = async (action: () => Promise<unknown>) => { await flush(); await action().catch(() => undefined); };
  const state = !design.published_at ? t`Badges print the built-in design until you publish.`
    : design.has_unpublished_changes ? t`Desks print the last published version until you publish.` : t`Desks print this version.`;
  return <div className="grid gap-1.5" role="group" aria-label={t`Publishing`}>
    <div className="flex flex-wrap items-center gap-2">
      {canEdit && !design.needs_approval ? <button type="button" className="desk-button-primary min-h-11" disabled={busy || blocked}
        onClick={() => void run(() => publish.mutateAsync({}))}>{t`Publish badge`}</button> : null}
      {canEdit && design.needs_approval && !pending ? <button type="button" className="desk-button-primary min-h-11"
        disabled={busy || blocked} onClick={() => void run(() => submit.mutateAsync({}))}>{t`Submit for approval`}</button> : null}
      {pending && design.can_approve ? <button type="button" className="desk-button-success min-h-11" disabled={busy}
        onClick={() => void run(() => approve.mutateAsync({ note: "" }))}>{t`Approve and publish`}</button> : null}
      <span className="text-sm text-muted">{pending ? t`Revision ${pending.revision} is waiting for approval.` : state}</span>
    </div>
    {failure ? <p role="alert" className="text-sm text-danger">{failure instanceof Error ? failure.message : t`That didn't work.`}</p> : null}
  </div>;
}
