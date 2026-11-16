import { render, screen, fireEvent } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { EventFeedbackFields, isWordRating } from './EventFeedbackFields'
import type { CustomFormQuestion } from '../../forms/customFormTypes'

const question: CustomFormQuestion = { id: 'experience', label: 'Workshop experience', type: 'single_choice', options: ['Excellent', 'Good', 'Okay', 'Poor'], required: true }
it('uses only a revision’s explicit word options and returns their literal stored value', () => {
  const change = vi.fn()
  render(<EventFeedbackFields schema={[question]} answers={{}} onChange={change} />)
  fireEvent.click(screen.getByRole('radio', { name: 'Good' }))
  expect(change).toHaveBeenCalledWith({ experience: 'Good' })
  expect(isWordRating({ ...question, options: ['1', '2', '3', '4'] })).toBe(false)
})
