import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import bootstrap from '../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json'
import { AnswerDateReview } from './AnswerDateReview'
import type { Application } from './types'

function application(revision = 2): Application {
  return { ...bootstrap.virtual_draft, version: 4, answers: [{ id: 'age', type: 'age_at_event', value: 21 }],
    answer_review: { event_date_revision: revision, as_of_date: '2026-12-01', locked: true, date_review_required: true } } as Application
}
describe('event date review', () => {
  it('requires explicit review and sends revision/date only, never the computed age', () => {
    const onReview = vi.fn(), view = render(<AnswerDateReview application={application()} pending={false} onReview={onReview} />)
    expect(screen.getByRole('button', { name: 'Confirm date review' })).toBeDisabled()
    fireEvent.click(screen.getByLabelText('I have reviewed my answers for this date.'))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm date review' }))
    expect(onReview).toHaveBeenCalledExactlyOnceWith({ expected_version: 4, event_date_revision: 2, as_of_date: '2026-12-01', confirmed: true })
    expect(JSON.stringify(onReview.mock.calls)).not.toContain('21')
    view.rerender(<AnswerDateReview application={application(3)} pending={false} onReview={onReview} />)
    expect(screen.getByRole('button', { name: 'Confirm date review' })).toBeDisabled()
  })
})
