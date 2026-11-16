// Lane r2-gap-misc, gap 17 (S7, #180): public choice fields become gallery filters.
// Local, untracked (#175): run in the test phase on the combined tree.
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { gallerySearchQuery, isGallerySearching } from './api';
import { galleryFilters } from './parsers';
import { GallerySearchBar } from './GallerySearchBar';

const TRACK = { key: 'track', label: 'Track', choices: ['Health', 'Climate'] };

describe('S7 gallery field filters', () => {
  it('sends each chosen field as field.<key>, in key order, and skips the empty ones', () => {
    expect(gallerySearchQuery({ fields: { track: '' } })).toBe('');
    expect(gallerySearchQuery({ q: 'rover', fields: { zone: 'North', track: 'Health' } }))
      .toBe('q=rover&field.track=Health&field.zone=North');
  });
  it('counts a field filter as searching', () => {
    expect(isGallerySearching({})).toBe(false);
    expect(isGallerySearching({ fields: { track: '' } })).toBe(false);
    expect(isGallerySearching({ fields: { track: 'Health' } })).toBe(true);
  });
  it('reads the offered filters and treats a missing list as none', () => {
    expect(galleryFilters({ count: 0, results: [] })).toEqual([]);
    expect(galleryFilters({ filters: [TRACK] })).toEqual([TRACK]);
    expect(() => galleryFilters({ filters: [{ key: 'track', label: 'Track', choices: [1] }] })).toThrow();
    expect(() => galleryFilters({ filters: 'track' })).toThrow();
  });
  it('renders one control per offered field and clears it with Any', () => {
    const onChange = vi.fn();
    const { rerender } = render(<GallerySearchBar value={{}} onChange={onChange} unavailable={false} filters={[TRACK]} />);
    const select = screen.getByLabelText('Track');
    expect([...(select as HTMLSelectElement).options].map(option => option.textContent)).toEqual(['Any', 'Health', 'Climate']);
    fireEvent.change(select, { target: { value: 'Climate' } });
    expect(onChange).toHaveBeenLastCalledWith({ fields: { track: 'Climate' } });
    rerender(<GallerySearchBar value={{ fields: { track: 'Climate' } }} onChange={onChange} unavailable={false} filters={[TRACK]} />);
    fireEvent.change(screen.getByLabelText('Track'), { target: { value: '' } });
    expect(onChange).toHaveBeenLastCalledWith({ fields: {} });
  });
  it('renders no field controls when none are offered', () => {
    render(<GallerySearchBar value={{}} onChange={() => {}} unavailable={false} />);
    expect(screen.queryByLabelText('Track')).toBeNull();
  });
});
