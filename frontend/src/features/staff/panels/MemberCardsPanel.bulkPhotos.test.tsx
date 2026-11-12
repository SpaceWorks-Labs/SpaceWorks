import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'

const idle = { data: undefined, isLoading: false, error: null, isPending: false, mutate: vi.fn(), variables: undefined }
const page = { data: { results: [], count: 0 }, isLoading: false, error: null }
vi.mock('./memberCards/api', () => ({ useMemberCards: () => page, useCardMemberships: () => ({ data: [] }),
  usePrintCard: () => idle, usePrintSheet: () => idle }))
vi.mock('./memberCards/apiCards', () => ({ memberCardJobsPath: () => '/jobs', useMemberCardSettings: () => ({ data: { email_available: false } }) }))
vi.mock('./memberCards/CardsRowDialogs', () => ({ useCardRowActions: () => ({ rowActions: () => [], dialogs: null, printSelected: vi.fn(), onReissue: vi.fn(), onRevoke: vi.fn() }) }))
vi.mock('./memberCards/CardsTable', () => ({ CardsTable: () => <p>cards table</p> }))
vi.mock('../../cards/cardJobs', () => ({ CardJobList: () => null, JOB_LABELS: { bulk_sheet: 'Print sheets', zip: 'ZIP', email: 'Email' },
  useStartCardJob: () => idle }))
vi.mock('../../cards/SheetPreviewDialog', () => ({ SheetPreviewDialog: () => null }))
vi.mock('../../organizations/idProgrammes/ProgrammesTab', () => ({ ProgrammesTab: () => null }))
vi.mock('./staffCards/StaffCardsTab', () => ({ StaffCardsTab: () => null }))

import { MemberCardsPanel } from './MemberCardsPanel'

it('puts "Upload many photos" in the All cards menu and opens the member-card bulk upload', async () => {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MemberCardsPanel makerspaceId={3} /></MemoryRouter></QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: /All cards/ }))
  fireEvent.click(await screen.findByRole('menuitem', { name: /Upload many photos/ }))
  expect(await screen.findByRole('checkbox', { name: /agreed to them being stored privately/ })).toBeVisible()
})
