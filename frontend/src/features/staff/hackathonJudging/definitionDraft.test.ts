import { describe, expect, it } from 'vitest';
import { changedFields } from './definitionDraft';

describe('definition patch safety', () => {
  it('omits unedited fields that another editor may have changed on the server', () => {
    const original = { name: 'Hardware', description: 'Original', capacity: 20 };
    expect(changedFields(original, { ...original, description: 'My updated description' }))
      .toEqual({ description: 'My updated description' });
  });
  it('includes explicit clears and compares structured rubrics by value', () => {
    expect(changedFields({ sponsor_id: 6, criteria: [{ key: 'build', weight: '1.0000' }] },
      { sponsor_id: null, criteria: [{ key: 'build', weight: '1.0000' }] })).toEqual({ sponsor_id: null });
  });
});
