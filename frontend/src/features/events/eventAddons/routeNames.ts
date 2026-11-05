/**
 * Member-facing travel-support, stage-form and payout pages. These literal paths match
 * the links the backend writes into notices (event_reimbursements/notices.py,
 * staged_forms/notices.py, event_payouts/notices.py), with an optional /m/:slug prefix.
 */
const PREFIXES = ["", "/m/:slug"] as const;
const EVENT_SUFFIXES = [
  "/member/events/:eventId/reimbursement",
  "/member/events/:eventId/reimbursement/:view",
  "/member/events/:eventId/stage-forms",
  "/member/events/:eventId/stage-forms/:stageFormId",
  "/member/events/:eventId/stage-responses/:responseId",
] as const;
const PAYOUT_SUFFIXES = ["/member/event-payouts", "/member/event-payouts/:obligationId"] as const;
/** Hack-money (#180 G3/G4/G6): the member's prizes across this space's events. */
const PRIZE_SUFFIXES = ["/member/prizes"] as const;

export const eventAddonPaths = PREFIXES.flatMap(prefix => EVENT_SUFFIXES.map(suffix => prefix + suffix));
export const eventPayoutPaths = PREFIXES.flatMap(prefix => PAYOUT_SUFFIXES.map(suffix => prefix + suffix));
export const prizePaths = PREFIXES.flatMap(prefix => PRIZE_SUFFIXES.map(suffix => prefix + suffix));

export function isEventAddonPath(path: string) {
  return /^\/(?:m\/[^/]+\/)?member\/events\/\d+\/(?:reimbursement(?:\/(?:request|claim|appeal))?|stage-forms(?:\/\d+)?|stage-responses\/\d+)\/?$/.test(path)
    || /^\/(?:m\/[^/]+\/)?member\/event-payouts(?:\/[0-9a-f-]{36})?\/?$/i.test(path)
    || /^\/(?:m\/[^/]+\/)?member\/prizes\/?$/.test(path);
}

export function memberEventAddonHref(slug: string, eventId: number, suffix: string) {
  return `${slug ? `/m/${encodeURIComponent(slug)}` : ""}/member/events/${eventId}/${suffix}`;
}
