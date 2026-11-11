import { describe, expect, it, vi } from 'vitest'
import { takeInvitationFragment } from './TeamInvitationPage'

describe('team invitation fragment', () => {
  it('removes the secret from navigation state before any request', () => {
    const token = 'a'.repeat(64), replace = vi.fn()
    expect(takeInvitationFragment({ hash: '#token=' + token, pathname: '/team/join', search: '' }, replace)).toBe(token)
    expect(replace).toHaveBeenCalledWith('/team/join')
  })
  it('clears a malformed token without forwarding it', () => {
    const replace = vi.fn()
    expect(takeInvitationFragment({ hash: '#token=bad', pathname: '/team/join', search: '' }, replace)).toBe('')
    expect(replace).toHaveBeenCalledOnce()
  })
})
