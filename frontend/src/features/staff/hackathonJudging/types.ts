import type { Envelope } from '../../events/hackathonGallery/types';
import type { RoundRead, AssignmentRead, CalculationRow, CriterionInput, TrackRead, PrizeRead, PairwiseStateRead } from '../../../generated/api';
export type Scope = { makerspaceId: number; eventId: number; actorId: number; context: string };
export type Criterion = CriterionInput;
export type ResultRow = CalculationRow;
export type JudgingMode = 'weighted_1_5' | 'top3' | 'pairwise';
export type Round = Omit<RoundRead, 'mode' | 'normalization'> & { mode: JudgingMode; normalization: 'none' | 'zscore' };
export type Assignment = Omit<AssignmentRead, 'mode' | 'configuration' | 'asset_ids' | 'batch_projects'> & {
  mode: JudgingMode; configuration: { criteria: Criterion[] }; asset_ids: number[];
  batch_projects: { snapshot_id: number; title: string }[] };
export type ResultState = Envelope & { sponsor_proposals?: { id: number; prize_id: number; submission_snapshot_id: number; created_at: string }[];
  aggregates: { rounds?: { round_id: number; rows: ResultRow[] }[];
  awards?: { prize_id: number; snapshot_id: number; rank: number; public_requested: boolean }[] } };
export type Track = Required<TrackRead>;
export type Prize = Required<PrizeRead>;
export type PairwiseAction = 'next' | 'compare' | 'skip' | 'recuse';
/** One judge's own cursor in a pairwise round: the project before, the one now, and progress. */
export type PairwiseState = Omit<PairwiseStateRead, 'allowed_actions'> & { allowed_actions: PairwiseAction[] };
