import { describe, expect, it } from 'vitest';
import { filterQuery, LISTS } from './EventStaffLists';

describe('event staff list filters', () => {
  it('sends only the filters the server allows for each list, never the page', () => {
    const values = { page: '3', q: 'robot', status: 'registered', state: 'locked', triage: 'eligible', below_target: 'true' };
    expect(filterQuery('guests', values)).toBe('status=registered&q=robot');
    expect(filterQuery('teams', values)).toBe('state=locked&q=robot');
    expect(filterQuery('submissions', values)).toBe('state=locked&triage=eligible&q=robot');
    expect(filterQuery('progress', values)).toBe('below_target=true');
    // E-B4 (D13): the results list searches the project title or prize name, so it sends `q` too.
    expect(filterQuery('results', values)).toBe('q=robot');
    expect(filterQuery('results', { page: '2' })).toBe('');
  });
  it('maps every list to a saved-view entity of 24 characters or fewer', () => {
    for (const list of Object.values(LISTS)) expect(list.entity.length).toBeLessThanOrEqual(24);
  });
});
