import { useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Modal } from '../../../components/ui'
import { staffRequest } from '../../../lib/api'
import type { BulkIssue, CertificateEligibility, CertificateKindEnum } from '../../../generated/api'
import type { RoleApplication } from '../../events/contributions/types'
import { sessionScope } from '../eventProgramme/sessionScope'

export function IssueRoleCertificate({ eventId, role }: { eventId: number; role: RoleApplication }) {
  const [open, setOpen] = useState(false), [publish, setPublish] = useState(false)
  const operation = useRef(crypto.randomUUID())
  const kind: CertificateKindEnum | undefined = role.role === 'volunteer' ? 'volunteer_thanks' : role.role === 'mentor' ? 'mentor_thanks' : role.role === 'judge' ? 'judge_thanks' : undefined
  const eligibility = useQuery({ queryKey: ['certificate-eligibility', eventId, ...sessionScope()], enabled: open, retry: false, staleTime: 0, gcTime: 0,
    queryFn: () => staffRequest<CertificateEligibility>(`/admin/events/${eventId}/certificates/eligibility/`) })
  const issue = useMutation({ mutationFn: async () => {
    if (!kind || !eligibility.data) throw new Error('Refresh this event before issuing the certificate.')
    const body: BulkIssue = { operation_id: operation.current, expected_version: eligibility.data.event_version,
      subjects: [{ subject_kind: 'role_assignment', subject_id: role.id, kind }], all_attended: false, publish_event_details: publish, confirmed_count: 1 }
    await staffRequest(`/admin/events/${eventId}/certificates/bulk/`, { method: 'POST', headers: { 'Idempotency-Key': operation.current }, body: JSON.stringify(body) })
  }, onSuccess: () => { setOpen(false); operation.current = crypto.randomUUID() } })
  if (!kind || role.state !== 'completed') return null
  return <div className="mt-4 grid gap-3">
    <button className="desk-button" onClick={() => setOpen(true)}>Issue thank-you certificate</button>
    {issue.isSuccess ? <p role="status">Certificate issuance queued. Its original contribution evidence will be verified before issuing.</p> : null}
    <Modal open={open} title="Issue this contribution certificate?" onClose={() => setOpen(false)}
      footer={<div className="flex flex-wrap gap-3"><button className="desk-button" onClick={() => setOpen(false)}>Cancel</button><button className="desk-button-primary"
        disabled={!eligibility.data || Boolean(eligibility.error) || issue.isPending} onClick={() => issue.mutate()}>Confirm issue</button></div>}>
      <div className="grid gap-3"><p>Issue one certificate for this completed {role.role} contribution. Contribution evidence and eligibility are checked again.</p>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={publish} onChange={event => { setPublish(event.target.checked); operation.current = crypto.randomUUID() }} />Enable public event, date and certificate status verification</label>
        {eligibility.error || issue.error ? <p role="alert" className="text-danger">{eligibility.error?.message || issue.error?.message}</p> : null}
      </div>
    </Modal>
  </div>
}
