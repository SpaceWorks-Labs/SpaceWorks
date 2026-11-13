import { t } from "@lingui/core/macro";
import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, ErrorText, StatusBadge } from '../../../components/ui'
import { CommandSession, readStaff } from '../../events/hackathonAdmission/transport'
import type { DecisionBatch, DecisionSelection } from './types'

export function DecisionBatchPanel({ eventId, selections, onReleased, resumeBatchId }: {
  eventId: number; selections: DecisionSelection[]; onReleased: () => void; resumeBatchId?: number | null
}) {
  const base = '/api/v1/admin/events/' + eventId, commands = useRef(new CommandSession()), client = useQueryClient()
  const [batch, setBatch] = useState<DecisionBatch | null>(null), [preview, setPreview] = useState<Record<string, unknown> | null>(null)
  const action = useMutation({ mutationFn: async (kind: 'preview' | 'stage' | 'release' | 'cancel' | 'refresh' | 'resume') => {
    if (kind === 'refresh' || kind === 'resume') return readStaff<DecisionBatch>(base + '/application-decisions/' + (kind === 'resume' ? resumeBatchId : batch!.id) + '/')
    const body = kind === 'preview' || kind === 'stage' ? { expected_version: 0, decisions: selections }
      : { expected_version: batch!.version, batch_id: batch!.id }
    return commands.current.send<Record<string, unknown>>(base + '/application-decisions/' + kind + '/', 'POST', body, true)
  }, onSuccess: (value, kind) => {
    if (kind === 'preview') { setPreview(value as unknown as Record<string, unknown>); return }
    setBatch(value as unknown as DecisionBatch)
    if (kind === 'release' || kind === 'cancel') { void client.invalidateQueries({ queryKey: ['staff-event-admission', eventId] }); onReleased() }
  } })
  return <Card><section className="grid gap-3" aria-label={t`Decision batch`}>
    <h2 className="title-section">{t`Review and release decisions`}</h2>
    <p className="text-sm text-muted">{t`Staging is private. Participants see a decision only after you release the batch. Offers reserve people, including every member of a sealed team.`}</p>
    <p className="text-sm text-ink">{t`${selections.length} selected application subjects.`}</p>
    {action.error ? <ErrorText message={action.error.message} /> : null}
    {preview ? <p role="status" className="break-words text-sm text-muted">{t`The current capacity preview is ready. ${((preview.selection as { skipped?: unknown[] } | undefined)?.skipped?.length ?? 0)} selected groups do not fit the available offer places.`}</p> : null}
    {resumeBatchId && (!batch || batch.id !== resumeBatchId) ? <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate('resume')}>{t`Resume private batch #${resumeBatchId}`}</button> : null}
    {!batch || batch.state !== 'draft' ? <div className="flex flex-wrap gap-2">
      <button className="desk-button" type="button" disabled={action.isPending || !selections.length} onClick={() => action.mutate('preview')}>{t`Preview capacity`}</button>
      <button className="desk-button-primary" type="button" disabled={action.isPending || !selections.length} onClick={() => action.mutate('stage')}>{t`Stage private decisions`}</button>
    </div> : <><StatusBadge status={batch.state} label={t`Private draft`} /><p className="text-sm text-ink">{t`Batch #${batch.id}: ${batch.decisions.length} decisions. Releasing sends the owner notices and starts the RSVP deadline.`}</p>
      <div className="flex flex-wrap gap-2"><button className="desk-button-primary" type="button" disabled={action.isPending} onClick={() => action.mutate('release')}>{t`Release this batch`}</button>
        <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate('refresh')}>{t`Refresh batch`}</button>
        <button className="desk-button-danger-outline" type="button" disabled={action.isPending} onClick={() => action.mutate('cancel')}>{t`Cancel private draft`}</button></div></>}
  </section></Card>
}
