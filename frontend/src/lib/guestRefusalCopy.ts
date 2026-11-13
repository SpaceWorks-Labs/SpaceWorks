import { t } from "@lingui/core/macro";

/**
 * Decision 223: plain-language copy for the guest-pass, day-pass, minors and guardian-consent
 * refusals (backend lanes L1a, L1b, L3b). `eligibilityMessage` falls through to this, so every
 * surface that already shows eligibility copy (borrowing, self-checkout, machine sessions,
 * presence) shows these too. Returns null for any other code.
 */
export function guestRefusalMessage(code: string | undefined): string | null {
  switch (code) {
    // Issuing and buying passes (makerspaces/guest_pass_issue.py, guest_pass_day.py).
    case "guest_not_eligible": return t`This person can't get a guest pass here. Ask space staff.`;
    case "already_member": return t`You're already a member here, so you don't need a pass.`;
    case "pass_exists_today": return t`There is already a pass for that day.`;
    case "pass_day_in_past": return t`A pass can't start on a day that has already passed. Pick today or a later day.`;
    case "visit_cap_reached": return t`This guest has reached the space's visit limit. Join as a member to keep coming.`;
    case "sponsor_not_member": return t`Only active members can bring a guest.`;
    case "sponsor_tenure": return t`You haven't been a member long enough to bring a guest yet.`;
    case "sponsor_presence_required": return t`Check in at the space first, then bring your guest.`;
    case "sponsor_limit": return t`You already have the most guests this space allows at once.`;
    case "charges_off": return t`This space isn't charging for passes right now. Ask staff for a free pass, or turn on membership charges before pricing one.`;
    case "product_unavailable": return t`That day pass isn't on sale any more.`;
    case "day_pass_sold_out": return t`Day passes are sold out for that day. Try another day.`;
    case "pass_not_live": return t`This pass isn't live: it has ended, was withdrawn, or hasn't started yet.`;
    case "no_waiver_published": return t`This space has no waiver published yet, so there is nothing to accept.`;
    case "source_not_found": return t`We couldn't find that ticket or pass on your account.`;
    // Using a pass on site (hardware_requests/guest_lending.py, machines, presence).
    case "guest_pass_required": return t`You need a live guest pass or a membership for this. Ask a member to bring you, buy a day pass, or ask staff.`;
    case "guest_pass_no_borrow": return t`Guest passes here don't include borrowing. Ask staff, or join as a member.`;
    case "guest_pass_on_site_only": return t`On a guest pass, items stay on site and are due back before your pass ends.`;
    case "guest_pass_deposit_required": return t`Borrowing on a guest pass needs a deposit, and this item has none set. Ask staff.`;
    case "guest_pass_no_machines": return t`Guest passes here don't include machine use.`;
    case "guest_pass_supervised_only": return t`On a guest pass you can use machines only in a supervised session led by an instructor.`;
    case "guest_pass_supervised_session": return t`Join an instructor's supervised session for this machine first.`;
    case "guest_pass_machine_access_required": return t`On a guest pass a space manager must give you access to this machine before you use it.`;
    case "account_not_in_space": return t`This person isn't a member, walk-in or guest-pass holder here. Issue a guest pass or add them as a walk-in first.`;
    // Minors and guardian consent (makerspaces/minors_guard.py).
    case "minor_not_admitted": return t`This space doesn't admit people under the age of majority.`;
    case "minor_below_minimum_age": return t`This person is below the space's minimum age.`;
    case "guardian_terms_missing": return t`The space hasn't published its guardian consent text yet. A Space Manager must publish it first.`;
    case "guardian_consent_required": return t`A parent or guardian must sign the consent form first.`;
    case "guardian_consent_expired": return t`The guardian consent has expired. A parent or guardian must sign it again.`;
    case "guardian_presence_required": return t`A parent or guardian must be checked in at the space too.`;
    case "minor_borrowing_not_allowed": return t`People under the age of majority can't borrow items here.`;
    case "minor_machines_not_allowed": return t`People under the age of majority can't use machines here.`;
    default: return null;
  }
}
