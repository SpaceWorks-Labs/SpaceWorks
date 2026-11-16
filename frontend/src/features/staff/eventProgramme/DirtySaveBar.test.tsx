import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DirtySaveBar } from './DirtySaveBar'

const base = { dirty: true, pending: false, onSave: vi.fn(), onDiscard: vi.fn() }
afterEach(() => { vi.restoreAllMocks(); vi.clearAllMocks() })

describe('DirtySaveBar', () => {
  it('renders nothing while clean, idle and error-free', () => {
    const { container } = render(<DirtySaveBar {...base} dirty={false} />)
    expect(container.textContent).toBe('')
  })

  it('offers Save and Discard when dirty and routes each click', () => {
    render(<DirtySaveBar {...base} />)
    expect(screen.getByText('You have unsaved changes.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    fireEvent.click(screen.getByRole('button', { name: 'Discard' }))
    expect(base.onSave).toHaveBeenCalledOnce()
    expect(base.onDiscard).toHaveBeenCalledOnce()
  })

  it('disables both buttons and says Saving while pending', () => {
    render(<DirtySaveBar {...base} pending />)
    expect(screen.getByText('Saving changes…')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Discard' })).toBeDisabled()
  })

  it('blocks Save (but not Discard) when blocked, and shows an error even if clean', () => {
    const { rerender } = render(<DirtySaveBar {...base} blocked />)
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Discard' })).toBeEnabled()
    rerender(<DirtySaveBar {...base} dirty={false} error="Version conflict." />)
    expect(screen.getByRole('alert').textContent).toBe('Version conflict.')
  })

  it('guards link navigation while dirty: cancel keeps the page, confirm lets it through', () => {
    render(<><DirtySaveBar {...base} /><a href="#elsewhere">Away</a></>)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const link = screen.getByText('Away')
    expect(fireEvent.click(link)).toBe(false)
    expect(fireEvent.click(link)).toBe(true)
    expect(confirm).toHaveBeenCalledTimes(2)
  })

  it('does not guard links or unload once clean, and removes the guard on unmount', () => {
    const confirm = vi.spyOn(window, 'confirm')
    const { rerender, unmount } = render(<><DirtySaveBar {...base} dirty={false} /><a href="#x">Away</a></>)
    fireEvent.click(screen.getByText('Away'))
    expect(confirm).not.toHaveBeenCalled()
    rerender(<><DirtySaveBar {...base} /><a href="#x">Away</a></>)
    const event = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    unmount()
    const after = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(after)
    expect(after.defaultPrevented).toBe(false)
  })
})
