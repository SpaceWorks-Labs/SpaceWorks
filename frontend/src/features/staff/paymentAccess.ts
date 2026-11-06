import type { PaymentRow } from "./paymentsApi";

const SUBJECT_ACTION: Record<PaymentRow["subject_type"], string> = {
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
  donation: "record_payment",
  sponsorship: "record_payment",
  submission_fee: "manage_events",
  team_registration: "manage_events",
  event_deposit: "manage_events",
  shop_order: "manage_shop",
};

/** Cash receipt authority is separate from forgiving debt or sending provider money. */
export function paymentAccess(actions: readonly string[], isSuperadmin: boolean, row: PaymentRow) {
  const subjectAuthority = isSuperadmin || actions.includes(SUBJECT_ACTION[row.subject_type]);
  const record = subjectAuthority || actions.includes("record_payment");
  return { record, waive: subjectAuthority, refund: row.status === "paid_offline" ? isSuperadmin || actions.includes("record_payment") : subjectAuthority };
}
