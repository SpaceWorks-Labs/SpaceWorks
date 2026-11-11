import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { EventProgrammePage } from './EventProgrammePage'
import fixture from '../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json'

vi.mock('./ProgrammeAccess', () => ({ ProgrammeAccess: ({ children }: { children: (actor: { id: number }) => React.ReactNode }) => children({ id: 17 }) }))
vi.mock('../hackathonAdmission/useAdmission', () => ({ useAdmission: () => ({ context: { data: { ...fixture.context,
  programme: { ...fixture.context.programme, capabilities: { ...fixture.context.programme.capabilities, 'events.hackathons': true }, finder_enabled: false } } } }) }))
vi.mock('../hackathonAdmission/HackathonApplicationPage', () => ({ HackathonApplicationPage: () => <p>Application and RSVP screen</p> }))
vi.mock('../hackathonAdmission/TeamPage', () => ({ TeamPage: () => <p>My own team screen</p> }))
vi.mock('./TeamJourney', () => ({ TeamJourney: ({ section }: { section: string }) => <p>{section} workflow</p> }))
vi.mock('../../../lib/tenant', () => ({ useTenant: () => ({ slug: 'host', mode: 'central' }) }))

it('navigates from the real application route to the team and project screens', () => {
  render(<MemoryRouter initialEntries={[`/m/${fixture.context.makerspace.slug}/events/${fixture.context.event.public_token}/programme/application`]}><Routes>
    <Route path="/m/:slug/events/:publicToken/programme/*" element={<EventProgrammePage />} />
  </Routes></MemoryRouter>)
  expect(screen.getByText('Application and RSVP screen')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('link', { name: 'Your team' }))
  expect(screen.getByText('My own team screen')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('link', { name: 'Project and files' }))
  expect(screen.getByText('project workflow')).toBeInTheDocument()
})
