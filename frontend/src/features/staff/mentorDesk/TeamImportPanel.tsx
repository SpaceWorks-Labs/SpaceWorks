import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { staffRequestBlob } from '../../../lib/api'
import { DetailLayout } from '../../../components/layouts'
import { ActionControl, Card, Field, StatusPill } from '../../../components/ui'
import { basePath, errorText, requestFor, useProgrammeCommand } from '../../events/contributions/api'
import type { Aggregate, EventScope } from '../../events/contributions/types'

interface ImportPreview extends Aggregate { preview_token: string; mapping_sha256: string; expires_at: string; practice_run_id: string | null; mapping_count: number }
export function TeamImportPanel({ scope, canExport = false }: { scope: EventScope; canExport?: boolean }) {
  const [file, setFile] = useState<File | null>(null)
  const [practice, setPractice] = useState(true)
  const [practiceRun] = useState(() => crypto.randomUUID())
  const operation = useRef(crypto.randomUUID())
  const preview = useMutation({ retry: false, mutationFn: async () => {
    if (!file || file.size > 1_000_000) throw new Error(t`Select a CSV or XLSX file below 1 MB.`)
    const data = new FormData()
    data.set('file', file); data.set('expected_version', '0'); data.set('operation_id', operation.current)
    if (practice) data.set('practice_run_id', practiceRun)
    return requestFor('admin')<ImportPreview>(`${basePath(scope, 'admin')}/teams-import/preview/`, { method: 'POST', body: data, headers: { 'Idempotency-Key': operation.current } })
  } })
  const commit = useProgrammeCommand(scope, 'admin')
  const download = useMutation({ retry: false, mutationFn: async (format: 'csv' | 'xlsx') => {
    const blob = await staffRequestBlob(`${basePath(scope, 'admin')}/teams-export/?format=${format}${practice ? `&practice_run_id=${practiceRun}` : ''}`)
    const url = URL.createObjectURL(blob)
    try {
      const link = document.createElement('a'); link.href = url; link.download = `event-${scope.eventId}-teams.${format}`
      document.body.appendChild(link); link.click(); link.remove()
    } finally { window.setTimeout(() => URL.revokeObjectURL(url), 1000) }
  } })
  return <DetailLayout title={t`Import team mappings`} state={{ status: 'ready' }} main={<Card>
    <p className="mb-4 text-sm text-muted">{t`Use one CSV or XLSX sheet with columns team_id, member_ids, and alias. Separate member account IDs with semicolons. Names and contact details are never used to guess accounts.`}</p>
    <Field label={t`Team mapping file`}><input className="desk-input min-h-11" type="file" accept=".csv,.xlsx" onChange={event => {
      setFile(event.target.files?.[0] ?? null); preview.reset(); operation.current = crypto.randomUUID()
    }} /></Field>
    <label className="my-4 flex min-h-11 items-center gap-3"><input type="checkbox" checked={practice} onChange={event => {
      setPractice(event.target.checked); preview.reset(); operation.current = crypto.randomUUID()
    }} />{t`Practice session`}</label>
    <p className="mb-4 text-sm text-muted">{t`Practice data cannot send notifications, enter production analytics, publish results, or issue certificates.`}</p>
    {(preview.error || commit.error || download.error) ? <p role="alert" className="mb-4 text-danger">{errorText(preview.error ?? commit.error ?? download.error)}</p> : null}
    {preview.data ? <div role="status" className="mb-4"><StatusPill label={preview.data.practice_run_id ? t`Practice` : t`Production`} tone="info" />
      <p>{t`${preview.data.mapping_count} validated mappings · Preview expires ${new Date(preview.data.expires_at).toLocaleTimeString(formatLocale())}`}</p></div> : null}
    <div className="flex flex-wrap gap-3"><ActionControl action={{ label: t`Validate and preview`, pending: preview.isPending, disabled: !file,
      disabledReason: !file ? 'Select a mapping file first.' : undefined, onClick: () => preview.mutate() }} />
      {preview.data ? <ActionControl primary action={{ label: t`Commit import`, pending: commit.isPending,
        confirm: { title: preview.data.practice_run_id ? t`Start this practice session?` : t`Import production team mappings?`, message: t`The validated mapping will be checked once more before it is committed.` },
        onClick: () => { if (preview.data) commit.mutate({ path: '/teams-import/commit/', version: preview.data.version,
          fields: { preview_token: preview.data.preview_token, mapping_sha256: preview.data.mapping_sha256 } }, { onSuccess: () => preview.reset() }) } }} /> : null}
    </div>
    {canExport ? <div className="mt-6 flex flex-wrap gap-3" aria-label={t`Export explicit team mappings`}>
      <ActionControl action={{ label: t`Export CSV`, pending: download.isPending, onClick: () => download.mutate('csv') }} />
      <ActionControl action={{ label: t`Export XLSX`, pending: download.isPending, onClick: () => download.mutate('xlsx') }} />
    </div> : null}
  </Card>} />
}
