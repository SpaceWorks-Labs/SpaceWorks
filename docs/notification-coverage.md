# Notification coverage after Phase 2

This is the complete trigger inventory from `audit-spec-notify.out.txt` (2026-10-16).
It is the target for the domain adapter lanes, not a claim that Phase 1 converted them.
The existing lifecycle dispatcher remains compatible through legacy envelopes.

Personal = every selected, enabled, verified and consented medium: email, in-app,
native push, Telegram, Slack, Mattermost, Discord, WhatsApp (Twilio or Meta).
Email fallback requires tenant and recipient permission and no unsubscribe. Native push
also requires an active device grant. Unconfigured channels never become recipients.
Rooms = configured staff-only Telegram/Slack/Mattermost/Discord/signed-webhook destinations,
using the existing recipient and machine/type/category scope. Requester and campaign bodies
never go to rooms. Staff and owners receive separate envelope bodies.

Each account owner is explicit; no address/name-to-chat inference. Existing verified email
delivery remains for external invitees without an account. Account-only booking, event,
payment and loan owners do not acquire a universal membership requirement.

| Trigger from audit | Target audience | Target channels / Phase-2 obligation |
|---|---|---|
| Hardware `submitted`, `accepted`, `rejected`, `issued`, `partially_returned`, `returned`, `closed_with_issue` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes; closed_with_issue bypasses personal email opt-out, but requires the email module |
| Legacy overdue `return_reminder`, for spaces without a loan policy | Borrower/custodian; scoped staff for staff variants only | Mandatory email remains independent of selected personal chat; preserve suppression, module exemptions and never-deferred policy |
| Loan-policy ladder: advance/due/overdue borrower `return_reminder` | Borrower/custodian; scoped staff for staff variants only | Mandatory email remains independent of selected personal chat; preserve suppression, module exemptions and never-deferred policy |
| Loan-policy `overdue_escalated` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Loan `deposit_raised`, `late_fee_raised` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Tool `back_available` watch | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Tool `problem_report.filed` | Authorized hardware staff | Staff personal + scoped room summary; no requester identity/body in a room beyond the approved staff summary |
| Printer service `submitted`, `accepted`, `started`, `rejected`, `completed` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Printer service `failed`, `collected` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Printer reprint creation | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Non-printer machine service `submitted`, `accepted`, `rejected`, `started`, `completed`, `failed`, `collected` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Maintenance `schedule_created`, `schedule_updated`, `schedule_deactivated`, `logged`, `schedule_completed` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Maintenance calendar `due_soon`, `overdue` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Usage-meter maintenance threshold | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Certification grant/renewal `granted`; `revoked` | Affected certified member and authorized machine-type staff | Member personal; separate machine-type-scoped staff personal + rooms |
| Certification `expiring`, `expired` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Certification daily expiry digest | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Inventory reorder-point `low_stock` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Consumable restock `low_stock`; procurement `procurement_received` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Event `published`, `cancelled`, `completed` | Authorized event staff and affected registration owners | Staff personal + rooms; separate attendee personal lifecycle fan-out against the live registration audience |
| Event registration `registration_created`, `registration_pending_approval`, `registration_waitlisted`, `registration_approved`, `registration_rejected`, `registration_cancelled`, `registration_promoted` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Event `registration_restored` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Event check-in `registration_attended` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Event series `series_published`, `series_cancelled`, `series_completed`, `series_generation_failed` | Authorized event staff; affected series registration owners | Staff personal + rooms; owner personal for publication/cancellation/completion; generation failure staff-only and never deferred |
| Event start `reminder` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Event broadcast campaign | Live campaign audience only | Personal selected channels; email retains verified-email/module/unsubscribe gates; live original sender authority + resource + audience rechecked every batch; no staff-room campaign bodies |
| Event bulk invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers |
| Event certificate creation/render/reissue/revoke | Certificate registration owner | Personal navigation notice to authenticated document; no bearer or recipient details in rooms |
| Booking `created`, `confirmed`, `rejected`, `cancelled`, `restored`, `completed`, `no_show` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Booking start `reminder` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Booking broadcast campaign | Live campaign audience only | Personal selected channels; email retains verified-email/module/unsubscribe gates; live original sender authority + resource + audience rechecked every batch; no staff-room campaign bodies |
| Booking arrival confirmation/reversal | Booking owner and authorized booking staff | Separate owner personal / staff personal + scoped room summaries if emitted by booking lane |
| Membership `request_pending`, `member_joined` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Membership welcome after activation; member verification | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Membership approval `approved` | Authorized membership staff and approved applicant | Staff personal + rooms; owner private activation/welcome notice, deduplicated with welcome mail |
| Membership/admission `declined`, `awaiting_payment`, `payment_due` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Membership `renewal_due`, `lapsed`, `renewal_failed`, `renewed`, `grace_started`, `cancelled` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Membership invitation/referral | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers |
| Member broadcast | Live campaign audience only | Personal selected channels; email retains verified-email/module/unsubscribe gates; live original sender authority + resource + audience rechecked every batch; no staff-room campaign bodies |
| Payments `charge_raised`, `payment_received`, `refund_issued` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes |
| Payments `payment_due_soon`, `payment_due_today`, `payment_overdue`, `payment_failed` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Payment receipt/invoice/credit-document `document_issued` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms |
| Staff account invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers |
| Event staff invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers |
| Booking-resource staff invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers |
| Organization invitation creation/revocation/redemption | Explicit inviter/invitee | Audit/shareable link remains; account-linked private notice if added; never infer a chat identity |
| API-access request resolved | Explicit requester; authorized staff | Separate requester personal and staff summaries; route legacy direct Telegram through staff envelope |
| Device `offline`, `recovered` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| Subdomain request resolved | Explicit requester; authorized staff | Separate requester personal and staff summaries; route legacy direct Telegram through staff envelope |
| Makerspace archive requested/resolved | Superadmins / requesting staff | Platform email remains ungated; tenant rooms are not equivalent recipients |
| Archive/tenant-exit custody alarm | Borrower/custodian; scoped staff for staff variants only | Mandatory email remains independent of selected personal chat; preserve suppression, module exemptions and never-deferred policy |
| Scheduled report ready | Authorized selected staff | Existing selected email/room; personal endpoint selection must preserve report disclosure authority; never post unrestricted report links |
| Stocktake scheduled/completed | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out |
| First email delivery failure | Authorized staff | In-app + selected staff personal; suppress recursive failure notification storms |
| Daily notification digest | Explicit recipient | Email only; rebuild from currently eligible sources; chat digest preferences refused |
| Password-reset link/OTP | Mailbox owner | Platform email only; synchronous/redacted authentication proof; never reroute |
| Email-verification OTP | Mailbox owner | Platform email only; synchronous/redacted authentication proof; never reroute |
| Authenticator-enrollment email confirmation | Mailbox owner | Platform email only; synchronous/redacted authentication proof; never reroute |
| Phone login/link OTP | Phone owner | Existing platform authentication SMS only; separate from WhatsApp consent |
| Delivery tests | Space Manager / own verified endpoint or selected staff room | Provider.test diagnostics, including both WhatsApp providers; no member data in body |
| Platform problem-check beat task | Operators | Cache/dashboard remains intentional; no notification trigger added |

Five module exemptions stay exactly `(account,password_reset)`, `(account,email_verification)`,
`(hardware,return_reminder)`, `(backup,archive_custody_alarm)`, `(backup,tenant_exit_custody_alarm)`.
`closed_with_issue` is a separate personal-opt-out exception. Bounce/complaint suppression wins
even for mandatory mail. Authentication and custody bodies must never enter staff rooms.

Provider proof contract: Telegram private `/start` with secret-header verification and both chat/from
identity; Slack workspace-bound OIDC; Mattermost configured-server OAuth; Discord identify OAuth;
WhatsApp signed matching inbound/opt-in reply. STOP revokes. Only verified inbound opens the WhatsApp
24-hour window; outside it an approved event/audience/locale template binding is required.

Loan deposit/late-fee notices and payment-family notices must share a stable financial source
identity/revision so the owner receives one charge notice rather than duplicate domain mail.

Every Phase-2 adapter registers a `NotificationSource(eligible, render?)`. Its live check reloads
source validity/revision, explicit owner or campaign audience, original sender authority and resource
state. The shared layer adds account standing, tenant servability, staff scope, channel gates,
preference, endpoint consent/verification and integration generation on every attempt and digest.
