import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { expectNoA11yViolations } from '../../../test/axe';
import { GalleryPrivacy } from './GalleryPrivacy';
import { ResumeSharing } from './ResumeSharing';

const { mutate } = vi.hoisted(() => ({ mutate: vi.fn() }));
vi.mock('./api', () => ({
  useSharing: () => ({ consents: { data: { results: [], sponsors: [{ id: 6, name: 'Maker Partner', disclosure_revision: 1 }] } }, mutate: { mutate, isPending: false } }),
  useGalleryConsent: () => ({ query: { data: { version: 4, metadata_public: true, publication_state: 'published', asset_ids: [201], link_ids: [] } }, mutate: { mutate, isPending: false } }),
}));
const scope = { makerspaceId: 9, eventId: 42, actorId: 17 };
describe('member privacy choices', () => {
  it('never defaults sponsor recruiting consent on and names the exact sponsor', async () => {
    const { container } = render(<ResumeSharing scope={scope} readyResumes={[{ id: 301, label: 'My event résumé' }]} />);
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    fireEvent.change(screen.getByRole('combobox', { name: 'Sponsor' }), { target: { value: '6' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Ready event résumé' }), { target: { value: '301' } });
    expect(screen.getByRole('button', { name: 'Grant recruiting access' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Grant recruiting access' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ version: 0,
      fields: { sponsor_id: 6, asset_id: 301, purpose: 'recruiting', consent: true, disclosure_revision: 1 } }), expect.anything());
    await expectNoA11yViolations(container);
  });
  it('requires a fresh choice after selecting a different résumé', () => {
    render(<ResumeSharing scope={scope} readyResumes={[{ id: 301, label: 'Original' }, { id: 302, label: 'Replacement' }]} />);
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.change(screen.getByRole('combobox', { name: 'Ready event résumé' }), { target: { value: '302' } });
    expect(screen.getByRole('checkbox')).not.toBeChecked();
  });
  it('clears local sharing choices when the signed-in account changes', () => {
    const { rerender } = render(<ResumeSharing scope={scope} readyResumes={[{ id: 301, label: 'Original' }]} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Sponsor' }), { target: { value: '6' } });
    fireEvent.click(screen.getByRole('checkbox'));
    rerender(<ResumeSharing scope={{ ...scope, actorId: 18 }} readyResumes={[]} />);
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('combobox', { name: 'Sponsor' })).toHaveValue('');
  });
  it('lets a nonleader withdraw all disclosure immediately without a leader approval step', async () => {
    const { container } = render(<GalleryPrivacy scope={scope} teamId={21} snapshotId={101} leader={false}
      items={[{ id: 201, kind: 'asset', label: 'Project slides' }]} />);
    expect(screen.queryByRole('button', { name: 'Save public selection' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Make the whole project private' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ version: 4,
      suffix: 'teams/21/gallery-consent/withdraw/', fields: { scope: 'all' } }), expect.anything());
    await expectNoA11yViolations(container);
  });
  it('withdraws only selected item IDs', () => {
    render(<GalleryPrivacy scope={scope} teamId={21} snapshotId={101} leader={false}
      items={[{ id: 201, kind: 'asset', label: 'Project slides' }, { id: 211, kind: 'link', label: 'Repository' }]} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Repository' }));
    fireEvent.click(screen.getByRole('button', { name: 'Make chosen items private' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ fields: { scope: 'items', asset_ids: [], link_ids: [211] } }), expect.anything());
  });
});
