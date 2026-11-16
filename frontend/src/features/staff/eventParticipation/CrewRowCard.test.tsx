import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CrewRowCard } from './CrewRowCard';
import type { CrewRow } from './api';

const row: CrewRow = { id: 3, version: 2, member_id: 9, name: 'Asha', crew_role: 'Door', state: 'approved', origin: 'staff',
  show_publicly: true, registration_id: 1, has_place: true, kind: 'mentor', position: 1, staff_hidden: false };
const props = { pending: false, onDecide: vi.fn(), onRemove: vi.fn() };
const drag = { onDragStart: vi.fn(), onDragOver: vi.fn(), onDrop: vi.fn(), onDragEnd: vi.fn() };

describe('crew row (C8/C13)', () => {
  it('shows the kind chip only while crew kinds are on', () => {
    const { rerender } = render(<ul><CrewRowCard row={row} kinds onSave={vi.fn()} {...props} /></ul>);
    expect(screen.getByText('Mentor')).toBeTruthy();
    rerender(<ul><CrewRowCard row={row} kinds={false} onSave={vi.fn()} {...props} /></ul>);
    expect(screen.queryByText('Mentor')).toBeNull();
  });

  it('edits role, kind and public visibility in one save', () => {
    const save = vi.fn();
    render(<ul><CrewRowCard row={row} kinds onSave={save} {...props} /></ul>);
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Role' }), { target: { value: 'AV desk' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Kind' }), { target: { value: 'judge' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /Hide from the public crew section/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(save).toHaveBeenCalledWith({ crew_role: 'AV desk', staff_hidden: true, kind: 'judge' });
  });

  it('never sends a kind while crew kinds are off, and marks hidden crew', () => {
    const save = vi.fn();
    render(<ul><CrewRowCard row={{ ...row, staff_hidden: true }} kinds={false} onSave={save} {...props} /></ul>);
    expect(screen.getByText('Hidden from the public page')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    expect(screen.queryByRole('combobox', { name: 'Kind' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(save).toHaveBeenCalledWith({ crew_role: 'Door', staff_hidden: true });
  });

  it('moves with the keyboard arrows and disables the edge moves', () => {
    const move = vi.fn();
    render(<ul><CrewRowCard row={row} kinds onSave={vi.fn()} {...props} reorder={{ index: 0, count: 3, move, drag, dragging: false }} /></ul>);
    expect(screen.getByRole('button', { name: 'Move Asha up' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Move Asha down' }));
    expect(move).toHaveBeenCalledWith(1);
  });
});
