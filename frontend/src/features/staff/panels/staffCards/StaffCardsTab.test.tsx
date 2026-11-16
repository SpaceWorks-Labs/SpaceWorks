import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'

vi.mock('./StaffCardsList', () => ({ StaffCardsList: () => <p>staff list</p> }))
vi.mock('./StaffNumbering', () => ({ StaffNumbering: () => <p>numbering</p> }))
vi.mock('./StaffCardDesign', () => ({ StaffCardDesign: () => <p>design</p> }))
vi.mock('./StaffCardJobs', () => ({ StaffCardJobs: () => <p>jobs</p> }))

import { StaffCardsTab } from './StaffCardsTab'

const show = () => render(<QueryClientProvider client={new QueryClient()}><StaffCardsTab makerspaceId={3} deskPrint={false} /></QueryClientProvider>)

it('offers the bulk photo upload on the staff register and opens it for staff cards', () => {
  show()
  fireEvent.click(screen.getByRole('button', { name: 'Upload many photos' }))
  expect(screen.getByRole('checkbox', { name: /agreed to them being stored privately/ })).toBeVisible()
})

it('keeps the bulk photo upload off the other staff card sections', () => {
  show()
  fireEvent.click(screen.getByRole('radio', { name: 'Numbering' }))
  expect(screen.queryByRole('button', { name: 'Upload many photos' })).toBeNull()
})
