import { t } from "@lingui/core/macro";
import type { Category } from "../../events/reimbursements/types";
import type { ClaimQueueRow, ClaimReviewDetail, Pool, PolicySettings, ProgrammeDetail, RequestReviewRow, ReviewLine } from "./types";

/**
 * The server's documented read shapes (`ReimbursementRequestPage`, `ReimbursementClaimDetail`,
 * `ProgrammeFinanceDetail`) mapped onto the console's view models. Every value a command later
 * pins (pool, decision sequence, obligation and attendance versions) comes from the server.
 */
type RawPool = Pool & { audience?: string };
type RawRequest = { id: number; version: number; state: string; currency: string; estimated_total_minor: number;
  category_estimates?: { category: Category }[]; owner_label?: string; allowed_actions?: string[];
  tiers?: { key: string; label: string; amount_minor: number }[]; kind?: string;
  budget?: { pool_id: number; pool_version: number; available_minor: number };
  award?: { version: number; state: string; reason_code: string } | null };
type RawClaim = { id: number; uuid: string; version: number; state: string; display_state?: string; owner_label?: string;
  currency?: string; claimed_minor?: number; effective_due_at: string; info_due_at: string | null; due_revision: number;
  current_revision: number | null; allowed_actions: string[]; payout: { version: number } | null;
  accepted_cap_minor?: number; pool_version?: number; decision_sequence?: number; decision_reason?: string;
  registration_id?: number | null; attendance_revision?: number; eligibility_revision?: number; attendance_eligible?: boolean;
  recommendations?: ClaimReviewDetail["recommendations"]; appeal_statement?: string | null; review_lines?: ReviewLine[] };
type RawProgramme = Partial<PolicySettings> & { initialized: boolean; id?: number; version?: number; currency?: string;
  finance_policy_revision?: number; pools?: RawPool[]; min_application_stage?: number | null };

const CLAIM_ACTIONS: Record<string, string> = { decide: "claim_decide", recommend: "claim_recommend", extend: "claim_extend",
  correct_decision: "claim_correct_decision" };

export function toRequestRow(raw: RawRequest): RequestReviewRow {
  return { id: raw.id, version: raw.version, state: raw.state, currency: raw.currency, kind: raw.kind,
    owner_label: raw.owner_label ?? t`Member ${raw.id}`, estimated_total_minor: raw.estimated_total_minor,
    categories: (raw.category_estimates ?? []).map(row => row.category),
    allowed_actions: (raw.allowed_actions ?? []).map(action => action === "decide" ? "request_decide" : action),
    expected_award_version: raw.award ? raw.award.version : null,
    budget: raw.budget, award: raw.award ?? null, tiers: raw.tiers ?? [] };
}

export function toClaimRow(raw: RawClaim): ClaimQueueRow {
  return { id: raw.id, version: raw.version, state: raw.display_state ?? raw.state, owner_label: raw.owner_label ?? t`Claim ${raw.id}`,
    currency: raw.currency ?? "", claimed_minor: raw.claimed_minor ?? 0, due_at: raw.info_due_at ?? raw.effective_due_at,
    allowed_actions: raw.allowed_actions.map(action => CLAIM_ACTIONS[action] ?? action) };
}

export function toClaimReview(raw: RawClaim): ClaimReviewDetail {
  const lines = raw.review_lines ?? [];
  const finance = lines.some(line => line.receipt_asset_id !== undefined);
  const row = toClaimRow(raw);
  return { ...row, allowed_actions: finance ? [...row.allowed_actions, "receipt_read"] : row.allowed_actions,
    uuid: raw.uuid, claim_revision_id: raw.current_revision ?? 0, decision_sequence: raw.decision_sequence ?? 0,
    obligation_version: raw.payout?.version ?? null, eligibility_revision: raw.eligibility_revision ?? 0,
    due_revision: raw.due_revision, attendance_revision: raw.attendance_revision ?? 0, registration_id: raw.registration_id ?? null,
    accepted_cap_minor: raw.accepted_cap_minor ?? 0, pool_version: raw.pool_version ?? 0, lines,
    attendance_eligible: Boolean(raw.attendance_eligible), recommendations: raw.recommendations ?? [],
    decision_reason: raw.decision_reason ?? "", appeal_statement: raw.appeal_statement ?? null };
}

const SETTING_KEYS = ["enabled", "request_phase", "request_opens_at", "request_closes_at", "award_mode", "tier_rules",
  "allowed_categories", "exclusions", "min_distance_km", "eligible_countries", "eligible_cohorts", "min_application_stage",
  "award_accept_days", "claim_due_at", "attendance_required", "require_project_submission", "required_submission",
  "required_submission_stage", "permitted_venue_sources", "category_limits"] as const;

export function toProgramme(raw: RawProgramme): ProgrammeDetail {
  if (!raw.initialized) return { initialized: false, allowed_actions: ["programme_initialize"] };
  const settings = Object.fromEntries(SETTING_KEYS.filter(key => key in raw).map(key => [key, raw[key]])) as unknown as PolicySettings;
  const pool = raw.pools?.find(item => (item.audience ?? "participants") === "participants");
  return { initialized: true, id: raw.id, version: raw.version, currency: raw.currency, policy_revision: raw.finance_policy_revision,
    settings, pool, pools: raw.pools ?? [], allowed_actions: ["programme_edit"] };
}
