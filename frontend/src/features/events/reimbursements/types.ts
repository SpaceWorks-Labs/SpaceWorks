import type { FileReference, FormSchemaV2, ItineraryValue, MoneyValue } from "../../forms/types";
import type { EventScope } from "../stagedForms/privateQueries";
export type ReimbursementScope = EventScope;
export type Category = "rail" | "air" | "bus" | "ground_transport" | "lodging";
export const CATEGORIES: Category[] = ["rail", "air", "bus", "ground_transport", "lodging"];
export type Versioned = { id: number; version: number; state: string; allowed_actions: string[] };
export type RequestSubmission = { submit: true; programme_id: number; programme_version: number;
  form: { schema_version: 2; form_id: string; revision: number };
  estimates: (MoneyValue & { category: Category })[]; itinerary: ItineraryValue; need_statement: string; distance_km?: string };
export type RequestContext = { programme_id: number; programme_version: number; schema: FormSchemaV2;
  currency: string; allowed_categories: Category[]; min_distance_km: string | null };
export type GrantRequest = { id: number; uuid: string; version: number; state: string; estimated_total_minor: number; currency: string;
  reason_code: string; reason: string; submission?: RequestSubmission };
export type Award = { id: number; uuid: string; version: number; state: string; amount_minor: number; currency: string; award_revision: number;
  accept_by: string; accepted_at: string | null; reason_code: string; calculation_snapshot: Record<string, unknown> };
export type ClaimLine = { line_uuid: string; category: Category; vendor: string; description: string; traveller: string;
  expense_date: string; original_amount_minor: number; original_currency: string; fx_rate: string; rate_date: string;
  rate_source: "manual" | "receipt"; source_note: string; route: ItineraryValue | Record<string, never>;
  receipt: (FileReference & { receipt_total_minor: number }) | null;
  lodging_starts_on?: string; lodging_ends_on?: string; lodging_nights?: number };
/** The owner's view of the payout ledger obligation an approval created (`ReimbursementPayoutSummary`). */
export type PayoutSummary = { id: string; version: number; currency: string; approved_minor: number;
  effective_paid_minor: number; remaining_minor: number; state: string };
export type ClaimDecision = { id: number; sequence: number; outcome: string; approved_total_minor: number; currency: string;
  reason_code: string; reason: string; decided_at: string };
/** Backend `ClaimFinanceDetail` as the owner reads it. Owner actions: edit, submit, appeal. */
export type ClaimSummary = { id: number; uuid: string; version: number; state: string; display_state: string;
  current_revision: number | null; effective_due_at: string; info_due_at: string | null; appeal_due_at: string | null;
  appeal_used: boolean; allowed_actions: string[]; payout: PayoutSummary | null;
  draft?: { lines?: ClaimLine[] } | null; decisions?: ClaimDecision[] };
export type ProgrammeSummary = { initialized: boolean; enabled?: boolean; currency?: string; request_phase?: string;
  request_closes_at?: string | null; claim_due_at?: string; allowed_categories?: Category[]; exclusions?: string[];
  attendance_required?: boolean; category_limits?: Partial<Record<Category, number>> };
/** Backend `MemberSummary`. Actions: create_request, submit_request, withdraw_request, accept_award, decline_award, create_claim. */
export type ReimbursementOverview = { available: boolean; allowed_actions: string[]; programme: ProgrammeSummary;
  request_context: RequestContext | null; request: GrantRequest | null; award: Award | null; claim: ClaimSummary | null };
