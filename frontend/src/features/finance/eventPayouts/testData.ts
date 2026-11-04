import type { PayoutDetail, PayoutEntry, PayeeContext } from "./types";
export const scope = { actorId: 1, makerspaceId: 2 };
export const payout: PayoutDetail = { id: "obligation", version: 3, event_id: 5, event_title: "Maker gathering", currency: "INR",
  approved_minor: 1000, effective_paid_minor: 0, remaining_minor: 1000, state: "open", eligibility_status: "eligible",
  eligibility_revision: 2, current_revision_sequence: 1, coordination_state: "detached", entries: [], holds: [], attachments: [],
  eligibility_evidence: { attendance_revision: 2, eligible: true },
  allowed_actions: ["view", "record", "amend", "cancel", "hold", "release_hold", "acknowledge_eligibility", "reveal_payee", "verify_payee", "request_payee_correction", "submit_payee"],
  payee: { id: "payee", version: 1, country: "IN", method: "cash", masked_details: "Routing details hidden", verified: true, state: "current" } };
export const entry: PayoutEntry = { id: "entry", amount_minor: 200, currency: "INR", method: "cash", reference: "CASH-1",
  paid_at: "2026-01-18T10:00:00Z", amends_id: null, is_void: false, payee_revision_id: "old-payee", allowed_actions: ["amend"] };
export const payeeContext: PayeeContext = { payee: null, allowed_actions: ["submit_payee"],
  templates: [["IN", "bank_transfer", "in_bank", 1], ["IN", "upi", "in_upi", 1], ["US", "bank_transfer", "us_bank", 1]],
  disclosure_version: 1, disclosure: "Routing details are used for this obligation and are visible to finance." };
