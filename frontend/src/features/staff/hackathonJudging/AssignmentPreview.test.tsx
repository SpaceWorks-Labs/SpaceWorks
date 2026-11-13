import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { StructuredApiError } from '../../../lib/api';
import { commandErrorText } from '../../events/programmeCommandErrors';
import { AssignmentPreview, type AssignPlan } from './AssignmentPreview';
import type { Round } from './types';

const round = { id: 4, key: 'Main round' } as unknown as Round;
const plan: AssignPlan = { pairs: [{ snapshot_id: 101, judge_role_assignment_id: 7 }, { snapshot_id: 102, judge_role_assignment_id: 8 }],
  dropped: [{ snapshot_id: 103, judge_role_assignment_id: 7 }], deficits: {}, coverage_complete: true, existing: 'replace',
  before_loads: { 7: 3, 8: 1 }, after_loads: { 7: 3, 8: 2 }, plan_fingerprint: 'abc' };

describe('assignment preview (D10)', () => {
  it('shows each judge before and after, the withdrawn rows, and applies the previewed plan', () => {
    const apply = vi.fn();
    render(<AssignmentPreview round={round} plan={plan} pending={false} stale={false} onApply={apply} onPreviewAgain={vi.fn()} onDiscard={vi.fn()} />);
    const judge8 = screen.getByRole('rowheader', { name: 'Judge 8' }).closest('tr')!;
    expect(judge8.textContent).toContain('+1');
    expect(screen.getByText('1 assignment would be withdrawn')).toBeTruthy();
    expect(screen.getByText('Project 103 from judge 7')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Apply this plan' }));
    expect(apply).toHaveBeenCalledOnce();
  });

  it('replaces Apply with "Preview again" once the fingerprint is stale', () => {
    const again = vi.fn();
    render(<AssignmentPreview round={round} plan={plan} pending={false} stale onApply={vi.fn()} onPreviewAgain={again} onDiscard={vi.fn()} />);
    expect(screen.getByText('This preview is out of date.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Apply this plan' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Preview again' }));
    expect(again).toHaveBeenCalledOnce();
    expect(commandErrorText(new StructuredApiError(409, { code: 'plan_changed', detail: 'x' }))).toBe('The assignment plan changed since the preview. Preview it again.');
  });

  it('cannot apply a plan that leaves projects short of judges', () => {
    render(<AssignmentPreview round={round} plan={{ ...plan, coverage_complete: false, deficits: { 101: 2 } }} pending={false} stale={false}
      onApply={vi.fn()} onPreviewAgain={vi.fn()} onDiscard={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Apply this plan' })).toBeDisabled();
    expect(screen.getByText('More judges are needed: project #101 needs 2 more.')).toBeTruthy();
  });
});
