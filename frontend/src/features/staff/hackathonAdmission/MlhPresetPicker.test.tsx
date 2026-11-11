import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MlhPresetPicker, type ProgrammeMlhPreset } from './MlhPresetPicker'

const schema: ProgrammeMlhPreset['schema'] = { schema_version: 2, form_id: 'mlh-application', revision: 1,
  questions: [{ id: 'work', type: 'long_text', label: 'What will you build?' }] }
const presets = [{ id: 'mlh', label: 'MLH application', schema }]
describe('optional sharing preset selection', () => {
  it('starts off and passes the authoritative F schema without auto-consenting', () => {
    const onSelect = vi.fn(), view = render(<MlhPresetPicker presets={presets} value={{}} disabled={false} onSelect={onSelect} />)
    expect(screen.getByLabelText('Application preset')).toHaveValue('')
    fireEvent.change(screen.getByLabelText('Application preset'), { target: { value: 'mlh' } })
    expect(onSelect).toHaveBeenCalledExactlyOnceWith(schema)
    expect(onSelect.mock.calls[0][0]).not.toHaveProperty('accepted')
    view.rerender(<MlhPresetPicker presets={presets} value={schema} disabled={false} onSelect={onSelect} />)
    expect(screen.getByLabelText('Application preset')).toHaveValue('mlh')
    fireEvent.change(screen.getByLabelText('Application preset'), { target: { value: '' } })
    expect(onSelect).toHaveBeenLastCalledWith(null)
  })
})
