import { t } from "@lingui/core/macro";
import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ErrorBlock, Field, Pagination } from '../../../components/ui'
import { memberRequest, memberRequestBlob } from '../../../lib/api'
import type { AssetResponse, ResumePage, UploadResponse, AssetCommandResponse } from '../../../generated/api'
import type { EventScope } from '../contributions/types'
import { ResumeSharing } from '../hackathonGallery/ResumeSharing'
import { uploadOrigins } from './uploadPolicy'
import { ownSavedDetails } from '../../accountSavedDetails/api'
import { savedDetailsKey } from '../../accountSavedDetails/types'
import { LogoLoader } from '../../../components/LogoLoader'

export function EventResumePanel({ scope }: { scope: EventScope }) {
  const [page, setPage] = useState(1), [file, setFile] = useState<File | null>(null), [copy, setCopy] = useState(false)
  const client = useQueryClient()
  const key = ['event-resumes', scope.accountId, scope.makerspaceId, scope.eventId] as const
  const base = `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/participant-resumes/`
  const rows = useQuery({ queryKey: [...key, page], queryFn: () => memberRequest<ResumePage>(`${base}?page=${page}`), gcTime: 0, retry: false,
    refetchInterval: query => query.state.data?.results.some(row => ['validating', 'promoting', 'uploaded'].includes(row.state)) ? 3000 : false })
  const saved = useQuery({ queryKey: savedDetailsKey(scope.accountId), queryFn: ownSavedDetails, enabled: copy, gcTime: 0, retry: false })
  const resume = saved.data?.fields.find(row => row.field_key === 'resume')
  const source = resume?.value && typeof resume.value === 'object' && 'asset_id' in resume.value ? resume.value : null
  const operation = useRef(crypto.randomUUID())
  const completion = useRef(crypto.randomUUID())
  const uploadRow = useRef<UploadResponse | null>(null)
  const refresh = async () => { await client.invalidateQueries({ queryKey: key }) }
  const upload = useMutation({ mutationFn: async () => {
    if (!file || file.size > 10 * 1024 ** 2 || !file.name.toLowerCase().endsWith('.pdf')) throw new Error(t`Choose a PDF résumé of at most 10 MiB.`)
    const row = uploadRow.current ?? await memberRequest<UploadResponse>(base, { method: 'POST', headers: { 'Idempotency-Key': operation.current },
      body: JSON.stringify({ filename: file.name, bytes: file.size, mime: 'application/pdf' }) })
    uploadRow.current = row
    const descriptor = row.upload
    if (descriptor?.method !== 'POST' || !descriptor.url || !descriptor.fields) throw new Error(t`The résumé upload is unavailable. Refresh and retry.`)
    const target = new URL(descriptor.url)
    if (!uploadOrigins().includes(target.origin) || target.username || target.password) throw new Error(t`The configured upload destination is unavailable.`)
    const body = new FormData()
    for (const [name, value] of Object.entries(descriptor.fields)) body.append(name, value)
    body.append('file', file)
    const response = await fetch(target.href, { method: 'POST', body, credentials: 'omit', cache: 'no-store', redirect: 'error' })
    if (!response.ok) throw new Error(t`Upload interrupted. Retry with the same file.`)
    return memberRequest<AssetCommandResponse>(`${base}${row.asset_id}/complete/`, { method: 'POST', headers: { 'Idempotency-Key': completion.current },
      body: JSON.stringify({ expected_version: row.version, generation: row.generation, operation_id: completion.current }) })
  }, onSuccess: async () => { setFile(null); uploadRow.current = null; operation.current = crypto.randomUUID(); completion.current = crypto.randomUUID(); await refresh() } })
  const mutate = useMutation({ mutationFn: async (row?: AssetResponse) => {
    const id = crypto.randomUUID()
    return row ? memberRequest(`${base}${row.asset_id}/`, { method: 'DELETE', headers: { 'Idempotency-Key': id },
      body: JSON.stringify({ expected_version: row.version, operation_id: id }) })
      : memberRequest(`${base}from-saved/`, { method: 'POST', headers: { 'Idempotency-Key': id },
        body: JSON.stringify({ saved_asset_id: source?.asset_id, saved_detail_version: resume?.version }) })
  }, onSuccess: refresh })
  return <section aria-label={t`Event résumé and sponsor sharing`} className="grid gap-5">
    <h2 className="title-panel">{t`Your event résumé`}</h2><p className="text-sm text-muted">{t`Files stay private. Copying a saved résumé creates a separate event copy. Sponsor recruiting access needs a separate choice below.`}</p>
    <Field label={t`PDF résumé`} hint={t`At most 10 MiB`}><input type="file" accept="application/pdf,.pdf" className="desk-input" disabled={upload.isPending}
      onChange={event => { setFile(event.target.files?.[0] ?? null); uploadRow.current = null; operation.current = crypto.randomUUID(); completion.current = crypto.randomUUID() }} /></Field>
    <button className="desk-button-primary" disabled={!file || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? t`Uploading résumé…` : t`Upload event résumé`}</button>
    <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={copy} onChange={event => setCopy(event.target.checked)} />{t`Choose a copy from my Saved details`}</label>
    {copy ? <button className="desk-button" disabled={!source || mutate.isPending} onClick={() => mutate.mutate(undefined)}>{t`Copy saved résumé to this event`}</button> : null}
    {copy && saved.isSuccess && !source ? <p>{t`No ready résumé is saved in your account.`}</p> : null}
    <ErrorBlock error={rows.error || upload.error || mutate.error || saved.error} onRetry={() => void rows.refetch()} />
    {rows.isPending ? <LogoLoader label={t`Loading event résumés…`} size={48} className="min-h-16 py-3" /> : null}
    {rows.data?.results.map(row => <article key={row.asset_id} className="grid gap-3 rounded-xl border border-line bg-panel p-4">
      <p>{row.filename || t`Résumé ${row.asset_id}`} · <span role="status">{row.state}</span></p>
      <div className="flex flex-wrap gap-3"><button className="desk-button" disabled={row.state !== 'ready'} onClick={() => {
        void memberRequestBlob(`${base}${row.asset_id}/download/`).then(blob => {
          const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = 'event-resume.pdf'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
        }).catch(() => void rows.refetch())
      }}>{t`Download my résumé`}</button><button className="desk-button" disabled={mutate.isPending || !row.allowed_actions.includes('delete')}
        onClick={() => mutate.mutate(row)}>{t`Delete event copy`}</button></div>
    </article>)}
    <Pagination page={page} count={rows.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((rows.data?.count ?? 0) / 24)} onChange={setPage} />
    <ResumeSharing scope={{ ...scope, actorId: scope.accountId }} readyResumes={(rows.data?.results ?? []).filter(row => row.state === 'ready')
      .map(row => ({ id: row.asset_id, label: row.filename || t`Résumé ${row.asset_id}` }))} />
  </section>
}
