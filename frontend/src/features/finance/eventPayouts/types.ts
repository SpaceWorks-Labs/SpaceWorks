/** Local wire contracts until G regenerates the shared OpenAPI client. */
export type FinanceScope = { actorId: number; makerspaceId: number };
export type PayoutAction = "view" | "export" | "record" | "amend" | "cancel" | "hold" | "release_hold"
  | "acknowledge_eligibility" | "reveal_payee" | "verify_payee" | "request_payee_correction"
  | "submit_payee" | "delete_payee";
export type Actionable = { allowed_actions?: readonly PayoutAction[] };
export const permits = (row: Actionable | undefined, action: PayoutAction) => row?.allowed_actions?.includes(action) === true;
export type Payout = Actionable & { id: string; version: number; event_id: number; event_title: string; currency: string;
  approved_minor: number; effective_paid_minor: number; remaining_minor: number;
  state: "open" | "settled" | "cancelled"; eligibility_status: "eligible" | "held" | "needs_acknowledgement";
  eligibility_revision: number; current_revision_sequence: number | null; coordination_state: "attached" | "detached" };
export type Payee = { id: string; version: number; state: string; country: string; method: string;
  template_key?: string; template_version?: number; masked_details: string; verified: boolean;
  correction?: { reason_code: string; note: string } | null };
export type PayeeProjection = Payee | { state: "payee_not_requested" } | null;
export const collectedPayee = (payee: PayeeProjection | undefined): Payee | undefined => payee && "id" in payee ? payee : undefined;
export type PayoutEntry = Actionable & { id: string; amount_minor: number; currency: string; method: string; reference: string;
  paid_at: string; amends_id: string | null; is_void: boolean; payee_revision_id: string | null };
export type Hold = Actionable & { id: string; kind: "eligibility" | "retention"; reason_code: string;
  note?: string; hold_until: string | null };
export type Receipt = { id: string; generation: number; mime: string; bytes: number; sha256: string;
  state: string; allowed_actions?: readonly "download"[] };
export type DecisionRevision = { id: number; sequence: number; kind: "decision" | "cancellation";
  approved_minor: number; reason_code: string; created_at: string; decision_summary: Record<string, unknown> };
export type PayoutDetail = Payout & { payee: PayeeProjection; entries: PayoutEntry[]; holds?: Hold[];
  attachments?: Receipt[]; revisions?: DecisionRevision[]; expected_pool_version?: number | null;
  eligibility_evidence?: Record<string, unknown> };
export type Page<T> = { count: number; results: T[]; next: string | null; previous: string | null };
export type Preview = Actionable & { id: string; expires_at: string; preview: { obligation_id: string; remaining_minor: number; currency: string; masked_payee: string }[] };
export type CurrencyTotals = { currency: string; pool_minor: number | null; awarded_minor: number | null;
  claimed_minor: number | null; approved_minor: number; paid_minor: number; awaiting_payout_minor: number;
  awaiting_payout_count: number; claim_ageing: { label: string; count: number; amount_minor: number }[] | null };
export type FinanceDashboardData = Actionable & { currencies: CurrencyTotals[]; pool_provider_available: boolean };
export type TemplateChoice = readonly [country: string, method: string, key: string, version: number];
export type PayeeContext = Actionable & { payee: PayeeProjection; templates: TemplateChoice[];
  disclosure_version: number; disclosure: string };
export type CommandResult = { id: string; version: number; state: string };
