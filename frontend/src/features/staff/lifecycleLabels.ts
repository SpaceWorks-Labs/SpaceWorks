import { t } from "@lingui/core/macro";
import { sentenceCase } from "../../lib/sentenceCase";

/** Display labels for server status codes. Unknown codes fall back to sentence-cased words. */
const pick = (labels: Record<string, string>, code: string) => labels[code] ?? sentenceCase(code);

export const invitationStateLabel = (code: string) => pick({
  active: t`Active`, pending: t`Pending`, invited: t`Invited`, accepted: t`Accepted`, declined: t`Declined`,
  revoked: t`Revoked`, expired: t`Expired`, canceled: t`Canceled`, cancelled: t`Cancelled`, used: t`Used`,
}, code);

export const emailLogStatusLabel = (code: string) => pick({
  sent: t`Sent`, failed: t`Failed`, pending: t`Pending`, sending: t`Sending`, skipped: t`Skipped`,
}, code);

export const stocktakeConditionLabel = (code: string) => pick({
  available: t`Available`, damaged: t`Damaged`, lost: t`Lost`, unknown: t`Unknown`,
}, code);

export const mentorLifecycleLabel = (code: string) => pick({
  proposed: t`Proposed`, active: t`Active`, ended: t`Ended`,
}, code);

export const mentorVisitStateLabel = (code: string) => pick({
  not_started: t`Not started`, waiting: t`Waiting`, in_progress: t`In progress`, visiting: t`Visiting`, done: t`Done`, skipped: t`Skipped`,
}, code);

export const reviewStatusLabel = (code: string) => pick({
  pending: t`Pending`, approved: t`Approved`, rejected: t`Rejected`,
}, code);

export const organizationRelationshipLabel = (code: string) => pick({
  owner: t`Owner`, manager: t`Manager`, affiliate: t`Affiliate`,
}, code);

/** OR-5: an organization's governance and granted makerspace actions, worded for the invitation form. */
export const organizationActionLabel = (code: string) => pick({
  manage_organization_profile: t`Edit the organization profile`, manage_organization_members: t`Manage organization members`,
  manage_events: t`Manage events`, manage_bookings: t`Manage bookings`, view_inventory: t`View inventory`,
  edit_inventory: t`Edit inventory`, accept_request: t`Accept requests`, reject_request: t`Reject requests`,
  assign_box: t`Assign boxes`, issue_request: t`Hand out requested items`, issue_direct_loan: t`Hand out items directly`,
  return_request: t`Take returns`, upload_evidence: t`Upload handover photos`, collect_service_request: t`Hand over finished machine jobs`,
  manage_qr: t`Manage QR codes`, manage_printing: t`Manage printing`, scan_member_cards: t`Scan member cards`,
  manage_member_cards: t`Manage member cards`, manage_members: t`Manage members`, view_finance: t`View finances`,
  record_payment: t`Record payments`, record_reimbursement_payout: t`Record reimbursement payouts`, view_audit: t`View the audit log`,
  view_id_programmes: t`View ID programmes`, manage_id_programmes: t`Manage ID programmes`,
  approve_card_designs: t`Approve card designs`, view_analytics: t`View analytics`,
  manage_member_units: t`Manage member units`, view_member_units: t`View member units`,
}, code);
