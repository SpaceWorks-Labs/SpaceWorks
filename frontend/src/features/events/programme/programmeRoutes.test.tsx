import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ProgrammeRoutes } from './ProgrammeRoutes'
import { isProgrammePath, programmeHref, programmeRoutePaths } from './routeNames'
import { availableJourneys } from './EventProgrammePage'
import bootstrap from '../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json'
import { parseProgrammeContext } from '../contracts/parsers'

vi.mock('./EventProgrammePage', async original => ({ ...await original<typeof import('./EventProgrammePage')>(), EventProgrammePage: () => <p>Programme mounted</p> }))
vi.mock('./ProgrammeAccess', () => ({ ProgrammeAccess: ({ children }: { children: (actor: { id: number }) => React.ReactNode }) => children({ id: 17 }) }))
vi.mock('../../accountSavedDetails/SavedDetailsPage', () => ({ SavedDetailsPage: ({ actorId }: { actorId: number }) => <p>Saved details for {actorId}</p> }))
vi.mock('../../accountActivity/SecurityActivityPage', () => ({ SecurityActivityPage: () => <p>Own security activity</p> }))
vi.mock('../eventPresentation/CertificateVerificationPage', () => ({ CertificateVerificationPage: () => <p>Certificate verification mounted</p> }))
vi.mock('./PublicProgrammePage', () => ({ PublicProgrammePage: ({ results }: { results?: boolean }) => <p>{results ? 'Public results mounted' : 'Public gallery mounted'}</p> }))
vi.mock('../../../lib/tenant', () => ({ useTenant: () => ({ slug: 'host', mode: 'central' }) }))

describe('programme route mounting', () => {
  it.each([
    ['/events/token/programme/application', 'Programme mounted'],
    ['/m/host/events/token/programme/project', 'Programme mounted'],
    ['/events/token/gallery', 'Public gallery mounted'],
    ['/m/host/events/token/gallery/project-id', 'Public gallery mounted'],
    ['/m/host/events/token/results', 'Public results mounted'],
    ['/certificates/verify/opaque-id', 'Certificate verification mounted'],
    ['/member/account/saved-details', 'Saved details for 17'],
    ['/m/host/member/account/security-activity', 'Own security activity'],
    ['/member/account/security-activity/', 'Own security activity'],
    ['/m/host/member/account/security-activity/', 'Own security activity'],
  ])('%s reaches its actual screen', (path, text) => {
    expect(isProgrammePath(path)).toBe(true)
    render(<MemoryRouter initialEntries={[path]}><ProgrammeRoutes /></MemoryRouter>)
    expect(screen.getByText(text)).toBeInTheDocument()
  })
  it('keeps ordinary event and staff routes in their existing routers', () => {
    for (const path of ['/events/token', '/m/host/events/token', '/admin/events', '/m/host/member/payments']) expect(isProgrammePath(path)).toBe(false)
    expect(programmeRoutePaths).toHaveLength(2)
    expect(programmeHref('token', 'team', 'host')).toBe('/m/host/events/token/programme/team')
  })
  it('advertises journeys only from the token context capabilities', () => {
    const context = parseProgrammeContext(bootstrap.context)
    context.programme.capabilities['events.mentoring'] = false
    context.programme.finder_enabled = false
    const sections = availableJourneys(context).map(row => row.suffix)
    expect(sections).toContain('application')
    expect(sections).toContain('team')
    expect(sections).not.toContain('finder')
    expect(sections).not.toContain('help')
    context.programme.capabilities['events.hackathons'] = false
    expect(availableJourneys(context).map(row => row.suffix)).not.toContain('project')
  })
})
