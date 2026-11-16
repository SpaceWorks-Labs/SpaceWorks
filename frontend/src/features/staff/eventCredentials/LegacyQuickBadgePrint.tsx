import { t } from "@lingui/core/macro";
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { staffRequest } from '../../../lib/api'
import type { BadgeDesignResult } from '../../../generated/api'
import { QuickPrintSheet } from './QuickPrintSheet'
import { useDeskPrint } from './api'
import { sessionScope } from '../eventProgramme/sessionScope'

export function LegacyQuickBadgePrint({ eventId, registrationId, name, onClose }: {
  eventId: number; registrationId: number; name: string; onClose: () => void
}) {
  const [, setParams] = useSearchParams()
  const design = useQuery({ queryKey: ['event-badge-desk-design', eventId, ...sessionScope()], retry: false, gcTime: 0, staleTime: 0,
    queryFn: () => staffRequest<BadgeDesignResult>(`/admin/events/${eventId}/badges/desk-design/`) })
  const print = useDeskPrint(eventId)
  return <><QuickPrintSheet open canPrint name={name} pending={print.isPending || design.isPending} printDisabled={!design.data || design.data.event_version === undefined} error={design.error ? "Save a current desk design before printing this ID card." : print.error?.message} onSkip={onClose}
    onEdit={() => { onClose(); setParams(previous => { const next = new URLSearchParams(previous); next.set('eventTab', 'certificates'); return next }) }}
    onPrint={() => {
      const row = design.data
      if (!row || row.event_version === undefined) return
      print.mutate({ registration_ids: [registrationId], expected_version: row.event_version, template_revision: row.id, stock: row.stock, include_photo: true },
        { onSuccess: result => {
          const url = URL.createObjectURL(result.blob), link = document.createElement('a'); link.href = url; link.download = 'event-id-card.pdf'; link.click()
          setTimeout(() => URL.revokeObjectURL(url), 1000); onClose()
        } })
    }} />
    {design.error || print.error ? <p role="alert" className="text-sm text-danger">{design.error ? t`Choose and save a current desk design before printing this ID card.` : print.error?.message}</p> : null}
  </>
}
