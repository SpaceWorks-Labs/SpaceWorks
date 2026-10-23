import type { Prize, Round, Track } from './types';

export function editableDefinition(row: Track | Prize | Round): Record<string, unknown> {
  if ('mode' in row) return { key: row.key, mode: row.mode, min_reviews: row.min_reviews, normalization: row.normalization,
    opens_at: row.opens_at ? new Date(row.opens_at).toISOString().slice(0, 16) + ':00Z' : null,
    closes_at: row.closes_at ? new Date(row.closes_at).toISOString().slice(0, 16) + ':00Z' : null,
    minutes_per_view: row.minutes_per_view, judging_minutes: row.judging_minutes,
    ...(row.mode === 'weighted_1_5' ? { criteria: row.criteria } : {}) };
  return { name: row.name, description: row.description, ...('award_count' in row ? {
    award_count: row.award_count, track_id: row.track_id, sponsor_id: row.sponsor_id, winner_selection_mode: row.winner_selection_mode,
  } : { capacity: row.capacity }) };
}

/** A PATCH contains the local changes only; server-owned/read-only fields never travel. */
export function changedFields(original: Record<string, unknown>, draft: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(draft).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(original[key])));
}
