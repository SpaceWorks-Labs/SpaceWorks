import { plural, t } from "@lingui/core/macro";
import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ErrorText, Field, Modal } from '../../../components/ui';
import { toast } from '../../../components/ui/toastStore';
import { CommandSession } from '../../events/hackathonAdmission/transport';
import { commandErrorText } from '../../events/programmeCommandErrors';

type Reinstated = { restored_assignments: number; skipped_assignments: number };

/**
 * D7: undo a disqualification. The project is eligible again, its judging work returns to judges who may still
 * judge it (scores were never deleted) and an open entry-fee refund case is voided. A reason is required.
 */
export function ReinstateDialog({ eventId, project, onClose }: {
  eventId: number; project: { id: number; version: number; title: string } | null; onClose: () => void }) {
  const [reason, setReason] = useState(''); const session = useRef(new CommandSession()); const client = useQueryClient();
  const reinstate = useMutation({ retry: false,
    mutationFn: () => session.current.send<Reinstated>(`/api/v1/admin/events/${eventId}/submissions/${project!.id}/reinstate/`, 'POST',
      { expected_version: project!.version, reason: reason.trim() }, true),
    onSuccess: result => {
      const restored = plural(result.restored_assignments, { one: '# judging assignment went back to its judge', other: '# judging assignments went back to their judges' });
      const kept = result.skipped_assignments ? ` ${plural(result.skipped_assignments, { one: '# stayed withdrawn (finished round, pairwise or a new conflict).', other: '# stayed withdrawn (finished rounds, pairwise or new conflicts).' })}` : '';
      toast(t`${project!.title} is reinstated. ${restored}.${kept}`);
      void client.invalidateQueries({ queryKey: ['programme-projects', eventId] });
      void client.invalidateQueries({ queryKey: ['hackathon-judging'] });
      setReason(''); onClose();
    } });
  const close = () => { if (!reinstate.isPending) { reinstate.reset(); setReason(''); onClose(); } };
  return <Modal open={!!project} onClose={close} title={t`Reinstate ${project?.title ?? ''}?`} footer={<div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
    <button type="button" className="desk-button w-full sm:w-auto" disabled={reinstate.isPending} onClick={close}>{t`Cancel`}</button>
    <button type="button" className="desk-button-primary w-full sm:w-auto" disabled={reinstate.isPending || !reason.trim()} onClick={() => reinstate.mutate()}>
      {reinstate.isPending ? t`Reinstating…` : t`Reinstate project`}</button></div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`The project becomes eligible again. Judging assignments it lost come back to judges who can still judge it, with their earlier scores. An open entry-fee refund is cancelled.`}</p>
      <Field label={t`Reason`} hint={t`Recorded in the event history.`}>
        <textarea className="desk-input min-h-24" maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></Field>
      {reinstate.error ? <ErrorText message={commandErrorText(reinstate.error)} /> : null}
    </div>
  </Modal>;
}
