import { expect, it } from 'vitest'
import { eventAccess } from '../eventStaffPermissions'
import { eventDrawerSurfaces } from '../eventDrawerTabs'
import type { StaffEvent } from '../eventsApi'
import { readinessHref } from './readinessHref'

const event = { status: 'published', ticketing_features: [], report_features: [], staff_permissions: ['review_applications'], can_manage_staff: false } as unknown as StaffEvent
it('keeps programme affordances off until their effective capability is present', () => {
  const access = eventAccess(event)
  const off = eventDrawerSurfaces(event, access).sections
  expect(off.applications).toBe(false)
  expect(off['programme-setup']).toBe(false)
  const on = eventDrawerSurfaces(event, access, ['events.hackathons', 'events.volunteering', 'events.mentoring']).sections
  expect(on.applications).toBe(true)
  expect(on['programme-setup']).toBe(false)
  expect(on.volunteers).toBe(false)
  expect(on['mentor-desk']).toBe(false)
})
it('maps readiness domain names into real scoped drawer destinations', () => {
  const result = readinessHref('/admin/events?event=42&tab=mentoring', 42, '/m/host/admin/events')
  expect(result).toContain('/m/host/admin/events?event=42&eventTab=mentor-desk')
  expect(readinessHref('/admin/events?event=43&tab=mentoring', 42, '/admin/events')).toBe('')
  expect(readinessHref('https://outside.example/admin/events?event=42&tab=teams', 42, '/admin/events')).toBe('')
})
