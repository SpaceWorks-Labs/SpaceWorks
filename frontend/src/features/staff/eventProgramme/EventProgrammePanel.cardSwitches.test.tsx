import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { StaffEvent } from '../eventsApi'
import { eventAccess } from '../eventStaffPermissions'
import { eventCredentialTools, eventDrawerSurfaces } from '../eventDrawerTabs'

vi.mock('@tanstack/react-query', async importOriginal => ({
  ...await importOriginal<typeof import('@tanstack/react-query')>(),
  useQuery: () => ({ data: { id: 17 } }),
}))
vi.mock('../EventCertificateDesigner', () => ({ EventCertificateDesigner: () => <p>Certificate designer mounted</p> }))
vi.mock('../eventCredentials/BulkCertificates', () => ({ BulkCertificates: () => <p>Bulk certificates mounted</p> }))
vi.mock('../eventBadges/DeskBadgeSwitch', () => ({ DeskBadgeSwitch: () => <p>Legacy desk badges mounted</p> }))
vi.mock('../eventCards/EventCardsPanel', () => ({ EventCardsPanel: () => <p>Event cards mounted</p> }))

import { EventProgrammePanel } from './EventProgrammePanel'

const event = (ticketing: string[] = [], permissions = ['edit_details']): StaffEvent => ({
  id: 31, ticketing_features: ticketing, staff_permissions: permissions, can_manage_staff: false,
} as unknown as StaffEvent)

describe('independent event credential switches', () => {
  it.each([
    [[], false, false],
    [['events.id_cards'], true, false],
    [['events.ticket_designs'], true, false],
    [['events.id_cards', 'events.ticket_designs'], true, false],
    [['events.certificate_designer'], false, true],
    [['events.id_cards', 'events.ticket_designs', 'events.certificate_designer'], true, true],
  ])('mounts only the enabled credential owners: %s', (features, cards, certificates) => {
    const row = event(features.filter(key => key === 'events.certificate_designer'))
    render(<EventProgrammePanel event={row} makerspaceId={2} section="certificates" access={eventAccess(row)} features={features} />)
    expect(Boolean(screen.queryByText('Event cards mounted'))).toBe(cards)
    expect(Boolean(screen.queryByText('Certificate designer mounted'))).toBe(certificates)
    expect(Boolean(screen.queryByText('Legacy desk badges mounted'))).toBe(certificates)
    expect(screen.queryByText('Bulk certificates mounted')).toBeNull()
    expect(eventDrawerSurfaces(row, eventAccess(row), features).sections.certificates).toBe(cards || certificates)
  })

  it.each([[], ['check_in'], ['manage_registrations'], ['publish_schedule']].map(permissions => ({ permissions })))('never widens card editing to another grant: $permissions', ({ permissions }) => {
    const row = event([], permissions)
    const access = eventAccess(row)
    render(<EventProgrammePanel event={row} makerspaceId={2} section="certificates" access={access} features={['events.id_cards', 'events.ticket_designs']} />)
    expect(screen.queryByText('Event cards mounted')).toBeNull()
    expect(screen.queryByText('Certificate designer mounted')).toBeNull()
    expect(screen.queryByText('Legacy desk badges mounted')).toBeNull()
    expect(eventDrawerSurfaces(row, access, ['events.id_cards', 'events.ticket_designs']).sections.certificates).toBe(false)
  })

  it('preserves the existing certificate-only check-in affordance without exposing card editing', () => {
    const row = event(['events.certificate_designer'], ['check_in'])
    const access = eventAccess(row)
    render(<EventProgrammePanel event={row} makerspaceId={2} section="certificates" access={access} features={['events.id_cards']} />)
    expect(screen.getByText('Legacy desk badges mounted')).toBeVisible()
    expect(screen.queryByText('Event cards mounted')).toBeNull()
    expect(screen.queryByText('Certificate designer mounted')).toBeNull()
    expect(eventCredentialTools(row, access, ['events.id_cards']).label).toBe('Certificates')
  })
})
