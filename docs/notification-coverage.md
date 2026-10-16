# Notification coverage after Phase 3 wiring

This is the complete trigger inventory from `audit-spec-notify.out.txt` (2026-10-16).
Checked against the merged producers and source registrations in `3fd2c82e` on 2026-10-17.
**TRUE means the stated producer/adapter is wired, not a runtime/provider test result.**
PARTIAL names a remaining part of the target; RETAINED means the existing intentional path.
All personal rows remain subject to the [integration limits](notification-contract.md#integration-limits-in-this-tree).
Member-token admission and authenticated OAuth completion/settings are wired; Meta is registered/mounted
but retains a blocking readiness gate. The existing lifecycle dispatcher remains compatible through
legacy envelopes.

Personal = every selected and eligible medium: email, in-app,
native push, Telegram, Slack, Mattermost, Discord, WhatsApp (Twilio or Meta).
Chat endpoints require verification and consent; narrow legacy email allowances are recorded below.
Email fallback requires tenant and recipient permission and no unsubscribe. Native push
also requires an active device grant. Unconfigured channels never become recipients.
Rooms = configured staff-only Telegram/Slack/Mattermost/Discord/signed-webhook destinations,
using the existing recipient and machine/type/category scope. Requester and campaign bodies
never go to rooms. Staff and owners receive separate envelope bodies.

Each account owner is explicit; no address/name-to-chat inference. Existing verified email
delivery remains for external invitees without an account. Account-only booking, event,
payment and loan owners do not acquire a universal membership requirement.

| Trigger from audit | Target audience | Channels / obligation | Code status (2026-10-17) |
|---|---|---|---|
| Hardware `submitted`, `accepted`, `rejected`, `issued`, `partially_returned`, `returned`, `closed_with_issue` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes; closed_with_issue bypasses personal email opt-out, but requires the email module | TRUE — request/staff/owner sources + guarded rooms; equipment email-policy limits [H] |
| Legacy overdue `return_reminder`, for spaces without a loan policy | Borrower/custodian; scoped staff for staff variants only | Mandatory email remains independent of selected personal chat; preserve suppression, module exemptions and never-deferred policy | TRUE — mandatory-email reminder producer; same-owner verified-contact compatibility leg [H] |
| Loan-policy ladder: advance/due/overdue borrower `return_reminder` | Borrower/custodian; scoped staff for staff variants only | Mandatory email remains independent of selected personal chat; preserve suppression, module exemptions and never-deferred policy | TRUE — revision-bound ladder intents; mandatory email plus selection [H] |
| Loan-policy `overdue_escalated` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — staff escalation source and scoped rooms [H] |
| Loan `deposit_raised`, `late_fee_raised` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — staff hardware summary; single owner charge through payments [H/O] |
| Tool `back_available` watch | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — watch source, latch, unsubscribe/rearm/visibility checks [H] |
| Tool `problem_report.filed` | Authorized hardware staff | Staff personal + scoped room summary; no requester identity/body in a room beyond the approved staff summary | TRUE — problem-report source and editor catalog event [H] |
| Printer service `submitted`, `accepted`, `started`, `rejected`, `completed` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — service source + owner/staff envelopes [H] |
| Printer service `failed`, `collected` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — service terminal-edge sources [H] |
| Printer reprint creation | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — reprinted service edge [H] |
| Non-printer machine service `submitted`, `accepted`, `rejected`, `started`, `completed`, `failed`, `collected` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | PARTIAL — producer wired; shared printing-module gate still refuses printing-off installs [H] |
| Maintenance `schedule_created`, `schedule_updated`, `schedule_deactivated`, `logged`, `schedule_completed` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — compatibility barrel delegates to the source-backed adapter [H] |
| Maintenance calendar `due_soon`, `overdue` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — calendar reaches the adapter through the maintenance barrel [H] |
| Usage-meter maintenance threshold | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — meter reaches the adapter through the maintenance barrel [H] |
| Certification grant/renewal `granted`; `revoked` | Affected certified member and authorized machine-type staff | Member personal; separate machine-type-scoped staff personal + rooms | TRUE — member + scoped staff sources [H] |
| Certification `expiring`, `expired` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — owner-only expiry source [H] |
| Certification daily expiry digest | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — live-count staff digest source [H] |
| Inventory reorder-point `low_stock` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — threshold source wired from availability [H] |
| Consumable restock `low_stock`; procurement `procurement_received` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — automatic low_stock and procurement barrel delegate to the adapter [H] |
| Event `published`, `cancelled`, `completed` | Authorized event staff and affected registration owners | Staff personal + rooms; separate attendee personal lifecycle fan-out against the live registration audience | TRUE — staff/rooms plus live registration-owner fan-out [E] |
| Event registration `registration_created`, `registration_pending_approval`, `registration_waitlisted`, `registration_approved`, `registration_rejected`, `registration_cancelled`, `registration_promoted` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — separate staff/delegate/owner envelopes [E] |
| Event `registration_restored` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — restored registration source [E] |
| Event check-in `registration_attended` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — attended registration source [E] |
| Event series `series_published`, `series_cancelled`, `series_completed`, `series_generation_failed` | Authorized event staff; affected series registration owners | Staff personal + rooms; owner personal for publication/cancellation/completion; generation failure staff-only and never deferred | TRUE — series fan-out; generation failure staff-only [E] |
| Event start `reminder` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — account-only reminder source, no membership dependency [E] |
| Event broadcast campaign | Live campaign audience only | Personal selected channels; email retains verified-email/module/unsubscribe gates; live original sender authority + resource + audience rechecked every batch; no staff-room campaign bodies | TRUE — channel envelopes; legacy worker owns email; no periodic channel-task resume [E] |
| Event bulk invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers | RETAINED — verified-email/share path; optional account-linked notice not added [E] |
| Event certificate creation/render/reissue/revoke | Certificate registration owner | Personal navigation notice to authenticated document; no bearer or recipient details in rooms | TRUE — owner navigation notices with live certificate state [E] |
| Booking `created`, `confirmed`, `rejected`, `cancelled`, `restored`, `completed`, `no_show` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — staff/owner/grant envelopes, legacy rooms and same-owner contact email compatibility [B] |
| Booking start `reminder` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — account-only personal reminder source plus same-owner contact email compatibility [B] |
| Booking broadcast campaign | Live campaign audience only | Personal selected channels; email retains verified-email/module/unsubscribe gates; live original sender authority + resource + audience rechecked every batch; no staff-room campaign bodies | TRUE — saved selections use envelopes; others batch email [B] |
| Booking arrival confirmation/reversal | Booking owner and authorized booking staff | Separate owner personal / staff personal + scoped room summaries if emitted by booking lane | NOT EMITTED — services_arrival records audit/history only [B] |
| Membership `request_pending`, `member_joined` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — lifecycle/application sources [O] |
| Membership welcome after activation; member verification | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — owner envelope + preserved direct-mail fallback [O] |
| Membership approval `approved` | Authorized membership staff and approved applicant | Staff personal + rooms; owner private activation/welcome notice, deduplicated with welcome mail | TRUE — approval/welcome share owner intent [O] |
| Membership/admission `declined`, `awaiting_payment`, `payment_due` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — application source; revoked-owner shared refusal still applies [O] |
| Membership `renewal_due`, `lapsed`, `renewal_failed`, `renewed`, `grace_started`, `cancelled` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — term sources and transactional reminder completion [O] |
| Membership invitation/referral | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers | TRUE — explicit account notice; existing contact email/share preserved [O] |
| Member broadcast | Live campaign audience only | Personal selected channels; email retains verified-email/module/unsubscribe gates; live original sender authority + resource + audience rechecked every batch; no staff-room campaign bodies | TRUE — audited producer calls notify_broadcast for each selected account [O] |
| Payments `charge_raised`, `payment_received`, `refund_issued` | Authorized staff and explicit domain owner | Separate staff personal + scoped room summaries and owner personal envelopes | TRUE — ledger owner/staff sources; no rail dependency [O] |
| Payments `payment_due_soon`, `payment_due_today`, `payment_overdue`, `payment_failed` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — pending-debt live checks and durable reminder revisions [O] |
| Payment receipt/invoice/credit-document `document_issued` | Explicit watcher/member/owner | Personal; preserve existing address eligibility and authenticated document links; no rooms | TRUE — document source plus preserved direct-mail fallback [O] |
| Staff account invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers | RETAINED — email/private-share; no optional chat notice [O] |
| Event staff invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers | RETAINED — email/private-share; no optional chat notice [E] |
| Booking-resource staff invitation | Explicit invitee | Verified email / manually shared invite for unknown accounts; proven accounts may receive private navigation notices; never room bearers | RETAINED — email/private-share; no optional chat notice [B] |
| Organization invitation creation/revocation/redemption | Explicit inviter/invitee | Audit/shareable link remains; account-linked private notice if added; never infer a chat identity | RETAINED — audit/share link; no account-linked notice added [O] |
| API-access request resolved | Explicit requester; authorized staff | Separate requester personal and staff summaries; route legacy direct Telegram through staff envelope | TRUE — private requester and staff source/room bodies [O] |
| Device `offline`, `recovered` | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | TRUE — immutable outage/recovery edge sources [O] |
| Subdomain request resolved | Explicit requester; authorized staff | Separate requester personal and staff summaries; route legacy direct Telegram through staff envelope | TRUE — private requester and staff source/room bodies [O] |
| Makerspace archive requested/resolved | Superadmins / requesting staff | Platform email remains ungated; tenant rooms are not equivalent recipients | RETAINED — ungated platform mail [O] |
| Archive/tenant-exit custody alarm | Borrower/custodian; scoped staff for staff variants only | Mandatory email remains independent of selected personal chat; preserve suppression, module exemptions and never-deferred policy | RETAINED — mandatory custody mail; no new personal-chat adapter [O] |
| Scheduled report ready | Authorized selected staff | Existing selected email/room; personal endpoint selection must preserve report disclosure authority; never post unrestricted report links | TRUE — selected role/action personal navigation; external email retained [O] |
| Stocktake scheduled/completed | Authorized scoped staff | Staff personal + scoped rooms; preserve machine/type/category narrowing; no default member fan-out | PARTIAL — producer and legacy inbox dedup wired; stock category still requires procurement [O] |
| First email delivery failure | Authorized staff | In-app + selected staff personal; suppress recursive failure notification storms | TRUE — first-failure source and legacy inbox mirror share intent/UUID deduplication [O] |
| Daily notification digest | Explicit recipient | Email only; rebuild from currently eligible sources; chat digest preferences refused | TRUE — email-only, source-revalidated personal digest [C] |
| Password-reset link/OTP | Mailbox owner | Platform email only; synchronous/redacted authentication proof; never reroute | RETAINED — synchronous/redacted platform email [C] |
| Email-verification OTP | Mailbox owner | Platform email only; synchronous/redacted authentication proof; never reroute | RETAINED — synchronous/redacted platform email [C] |
| Authenticator-enrollment email confirmation | Mailbox owner | Platform email only; synchronous/redacted authentication proof; never reroute | RETAINED — email-only authentication proof [C] |
| Phone login/link OTP | Phone owner | Existing platform authentication SMS only; separate from WhatsApp consent | RETAINED — existing SMS authentication [C] |
| Delivery tests | Space Manager / own verified endpoint or selected staff room | Provider.test diagnostics, including both WhatsApp providers; no member data in body | PARTIAL — both factories registered; Meta readiness still requires an unregistered module [C] |
| Platform problem-check beat task | Operators | Cache/dashboard remains intentional; no notification trigger added | RETAINED — cache/dashboard, no new trigger [O] |

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

Source-backed adapters register `NotificationSource(eligible, render?)`; each applies its domain's
live ownership/state/revision or sender/audience checks. The shared personal layer adds account
standing, tenant servability, staff scope, channel gates, preference, endpoint consent/verification
and generation on each attempt/digest. Room source revalidation is implemented for equipment;
other room summaries retain legacy retry policy. Registration alone does not wire a producer.

Presence adds a separate TRUE producer: `presence/notifications.py` emits `presence.expiry` at
expiry, default in-app/native push, no email fallback. Revision/new-session checks and the ten-minute
window suppress stale prompts. The catalog has the event, but the feature enum/editor lacks it.

Code ownership for the status column (all paths under `backend/apps/`):

- **[H] Equipment:** `hardware_requests/notifications_p2*.py`, `inventory/notifications_p2.py`,
  `machines/notifications_p2_{service,certifications,maintenance,stock}.py`; actual barrel/callers
  are indexed in [SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md). Maintenance/procurement
  barrels now delegate; shared generic-machine/email limits remain. `hardware.owner_mailbox`
  preserves the owner's same verified contact mailbox separately from the shared resolver.
- **[E] Events:** `events/notifications.py`, `notification_envelopes.py`, `notification_sources.py`,
  `broadcast_channels.py`, `reminders.py` and `services_certificates.py`. Staff in-app/push and
  campaign email are pre-skipped in envelopes because existing paths own them. Invitations retain
  their existing delivery; account-only history/reminders do not acquire a Membership dependency.
- **[B] Bookings:** `bookings/notifications.py`, `notification_sources.py`, `reminder_envelopes.py`,
  `broadcasts_personal.py`, `notification_owner_mailbox.py`, `services_arrival.py`. The email-only
  owner compatibility source preserves an unverified account's same booking contact address for
  lifecycle/reminders; live gates and one reserved email leg prevent parallel envelope mail.
  Whitelisted operational staff email allows active unverified staff; campaigns keep verified-email
  gates. Account-less guest contact mail remains. No arrival notification trigger is introduced.
- **[O] Other:** `makerspaces/notifications_p2*.py`, `payments/notifications_p2.py`,
  `apiclients/notifications_p2.py`, `devices/notifications_p2.py`, `operations/notifications_p2*.py`.
  `operations/notifications_p2.direct_mail_unless_routed` preserves existing welcome/verification/
  invitation/document mail without duplicating an envelope email leg. `notifications/broadcasts.py`
  calls `notifications_p2_broadcasts.notify_broadcast`. Stocktake/first-failure legacy inbox mirrors
  share source intent and UUID identity with personal delivery; scheduled-report legacy sent
  status is not transport proof. Archive/custody and invitations retain existing producer ownership.
- **[C] Contract:** `integrations/notification_{outbox,resolution,delivery,digest,proofs}.py`,
  `notification_api_*.py`, provider registration in `integrations/apps.py` and mounts in `urls.py`.
  `notification_catalog.py` now lists problem_report.filed, membership joined/verified/invitation/
  vouched, document_issued, subdomain/report/email-failure and stocktake events. Presence remains
  absent from the feature enum/editor. `notification_resolution.legacy_staff_email_allowed`
  narrowly preserves operational unverified staff email, never campaigns or requester/member mail.
