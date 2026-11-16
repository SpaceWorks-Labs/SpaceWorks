import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiPath, CommandSession } from './transport'
import { memberRequest } from '../../../lib/api'
vi.mock('../../../lib/api', () => ({ memberRequest: vi.fn(), staffRequest: vi.fn() }))
afterEach(() => vi.clearAllMocks())

describe('private command transport', () => {
  it.each(['https://foreign.test/api/v1/', '//foreign.test/api/v1/', '/api/v1/../private/', '/api/v1/%2e%2e/private/', '/api/v1/x/?secret=1'])('refuses foreign or ambiguous route %s', url => {
    expect(() => apiPath(url)).toThrow()
  })
  it('keeps the same operation UUID after a lost response and changes it after success', async () => {
    const request = vi.mocked(memberRequest)
    request.mockRejectedValueOnce(new Error('Network response lost')).mockResolvedValue({ id: 61 })
    const session = new CommandSession(), url = '/api/v1/member/makerspaces/9/events/42/application/submit/'
    const body = { expected_version: 0, answers: { institution: 'Maker College' } }
    await expect(session.send(url, 'POST', body)).rejects.toThrow('lost')
    await session.send(url, 'POST', body)
    const calls = request.mock.calls
    expect(calls[0][1]?.headers).toEqual(calls[1][1]?.headers)
    expect(calls[0][1]?.body).toBe(calls[1][1]?.body)
    await session.send(url, 'POST', body)
    expect(request.mock.calls[2][1]?.headers).not.toEqual(calls[0][1]?.headers)
  })
})
