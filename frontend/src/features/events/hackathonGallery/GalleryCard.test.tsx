import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fixtures from './domain-fixtures.test.json';
import { expectNoA11yViolations } from '../../../test/axe';
import { galleryEntry } from './parsers';
import { GalleryCard } from './GalleryCard';

describe('live-consented project card', () => {
  it('has accessible downloads and safe external links', async () => {
    const download = vi.fn().mockResolvedValue(undefined);
    const { container } = render(<GalleryCard entry={galleryEntry(fixtures.gallery_entry)} onDownload={download} />);
    fireEvent.click(screen.getByRole('button', { name: 'Download slides' }));
    await waitFor(() => expect(download).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('link', { name: /repo/ })).toHaveAttribute('rel', 'noopener noreferrer external');
    await expectNoA11yViolations(container);
  });
  it.each(['expired', 'withdrawn'] as const)('never renders a download control for %s files', state => {
    render(<GalleryCard entry={{ ...galleryEntry(fixtures.gallery_entry), files_state: state }} onDownload={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /Download/ })).toBeNull();
    expect(screen.getByText('Shared sensor')).toBeVisible();
  });
  it('surfaces revocation from a gateway without pretending the cached card grants access', async () => {
    render(<GalleryCard entry={galleryEntry(fixtures.gallery_entry)} onDownload={vi.fn().mockRejectedValue(new Error('This item is no longer public.'))} />);
    fireEvent.click(screen.getByRole('button', { name: 'Download slides' }));
    expect(await screen.findByText('This item is no longer public.')).toBeVisible();
  });
});
