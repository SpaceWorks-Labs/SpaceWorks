import type { PaymentRow } from "./paymentsApi";

export const SUBJECT_ACTION: Record<PaymentRow["subject_type"], string> = {
  machine_service_request: "manage_machines",
  booking: "manage_bookings",
  event_registration: "manage_events",
  makerspace_membership: "manage_makerspace",
  membership_term: "manage_makerspace",
  // Mirrors reconciliation_authority.SUBJECT_ACTIONS: admission fees are settled by whoever admits members.
  membership_request: "manage_members",
  membership_term_start: "manage_members", // #184: a staff-opened term
  loan_deposit: "issue_request",
  loan_late_fee: "return_request",
  loan_rental: "return_request",
  loan_damage: "return_request",
  loan_lost: "return_request",
  machine_session: "manage_machines",
  event_order: "manage_events",
  event_venue_fee: "manage_events",
  donation: "manage_donations", // decision 242(m): the Fundraising role and the Space Manager
  sponsorship: "manage_donations",
  submission_fee: "manage_events",
  team_registration: "manage_events",
  event_deposit: "manage_events",
  shop_order: "manage_shop",
};

/** Gifts and sponsor money are never an area manager's (decision 242(m), `area_queue.FINANCE_ONLY`). */
export const FINANCE_ONLY = new Set<string>(["donation", "sponsorship"]);

/**
 * Actions that own at least one charge type outside the finance-only subjects, i.e. the actor has an
 * own-area Payments queue (decision 242(a), `area_queue.owned_subject_types`). Guest passes are the
 * people area's (manage_members) on the server too.
 */
export const AREA_CHARGE_ACTIONS: readonly string[] = [...new Set(Object.entries(SUBJECT_ACTION)
  .filter(([subject]) => !FINANCE_ONLY.has(subject)).map(([, action]) => action))];

/** The handout desk's own money: loan deposits and fees follow issue/return authority (decision 217(b)). */
export function ownsLoanCharges(actions: readonly string[]) {
  return actions.includes("issue_request") || actions.includes("return_request");
}

export function ownsAreaCharges(actions: readonly string[]) {
  return AREA_CHARGE_ACTIONS.some(action => actions.includes(action));
}

/**
 * Cash receipt authority is separate from forgiving debt or sending provider money.
 * Decision 242(c): the area's own manager also hands back cash on an offline-paid charge of their
 * area (`CASH_RECORD_ACTIONS`), like the shop; gifts and sponsorship stay `record_payment` money.
 */
export function paymentAccess(actions: readonly string[], isSuperadmin: boolean,
  row: Pick<PaymentRow, "subject_type" | "status">) {
  const subjectAuthority = isSuperadmin || actions.includes(SUBJECT_ACTION[row.subject_type]);
  const record = subjectAuthority || actions.includes("record_payment");
  const cash = record && (!FINANCE_ONLY.has(row.subject_type) || isSuperadmin || actions.includes("record_payment"));
  return { record, waive: subjectAuthority, refund: row.status === "paid_offline" ? cash : subjectAuthority };
}
