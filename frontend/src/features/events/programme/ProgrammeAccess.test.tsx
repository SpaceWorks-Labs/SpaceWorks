import { useEffect, useState } from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { ProgrammeAccess } from './ProgrammeAccess'
import { notifySessionCleared } from '../../../lib/api/sessionContext'

vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(),
  getAccessToken: () => '', memberRequest: vi.fn(async () => ({ id: 17, username: 'Maker', display_name: 'Maker', kind: 'person' })),
}))
const released = vi.fn()
function Draft() {
  const [text, setText] = useState('')
  useEffect(() => () => released(), [])
  return <label>Private draft<input value={text} onChange={event => setText(event.target.value)} /></label>
}
it('mounts an account-only programme and clears drafts and resource effects on session loss', async () => {
  render(<MemoryRouter><ProgrammeAccess>{actor => <><p>Account {actor.id}</p><Draft /></>}</ProgrammeAccess></MemoryRouter>)
  const input = await screen.findByLabelText('Private draft')
  expect(screen.getByText('Account 17')).toBeInTheDocument()
  fireEvent.change(input, { target: { value: 'private bytes' } })
  act(() => notifySessionCleared('person'))
  await waitFor(() => expect(screen.getByLabelText('Private draft')).toHaveValue(''))
  expect(released).toHaveBeenCalled()
  expect(screen.getByRole('link', { name: 'Saved details' })).toHaveAttribute('href', '/member/account/saved-details')
})
