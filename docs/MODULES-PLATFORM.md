# Module reference

[Module guide and feature switches](MODULES.md)

## Notifications

Each channel is its own module, so a space that lives in Discord ships no Slack surface at all. Turning a
channel on never makes it start sending: you still add the webhook or token, and you still enable the
events you want in the per-feature × per-channel matrix. Turning it off stops delivery but **keeps the
stored credential**, so re-enabling needs no re-entry.

### notifications

- **What it is** — the in-app notification inbox and the emitters that feed it.
- **What it adds** -- the inbox, unread state and its optional feature-cell preference editor.
  Canonical personal intents live in core integrations; creating an inbox row never triggers push.
- **Without it** -- no in-app notifications. Canonical SMS/WhatsApp and native push remain
  independently gated; retained room/email paths keep their own rules. Other personal chat
  providers still require the notifications module in the shared resolver. Removing this
  inbox module differs from deployment-tombstoning its app.
- **Data** -- purgeable: in-app notification rows. Per-device canonical delivery children keep
  their envelope parent and optional SET_NULL inbox link; deleting inbox does not delete send history.
  Disabling this module differs from tombstoning the whole notifications app, which owns the
  registered push adapter.

### email

- **What it is** — outbound email **for this makerspace**.
- **What it adds** — tenant email delivery using the space's own SMTP credentials.
- **Without it** — the space sends no tenant email. **Account recovery and email verification still
  send**: those are platform mail (`makerspace=None`) and are deliberately exempt, or switching a module
  off could lock people out of their own accounts.
- **Data** — `purge_module_data` reports it stores no data of its own to purge separately.

### telegram

- **What it is** — per-makerspace Telegram group alerts. Outbound only.
- **What it adds** — the `telegram_alerts` workflow and test alerts. **No accept/reject buttons**: chat is
  a notification channel, not a decision surface, so an alert names the request and points staff at the
  console. The webhook route survives but acknowledges and discards every callback, which stops Telegram
  retrying against a deployment that already ran `setWebhook`.
- **Without it** — no Telegram alerts. Request decisions are unaffected; they are made in the staff console
  or `/control/` either way.
- **Data** — purgeable: Telegram destinations and their chat ids. Delivery logs survive — the record that
  a message was attempted is history; the credential is the secret.

### slack

- **What it is** — per-makerspace Slack alerts through an incoming webhook.
- **What it adds** — Slack as a destination in the notification matrix.
- **Without it** — no Slack surface ships at all for this space.
- **Data** — purgeable: Slack destinations and their stored webhooks (delivery logs survive).

### mattermost

- **What it is** — per-makerspace Mattermost alerts through an incoming webhook.
- **What it adds** — Mattermost as a destination in the notification matrix.
- **Without it** — no Mattermost surface ships at all for this space.
- **Data** — purgeable: Mattermost destinations and their stored webhooks (delivery logs survive).

### discord

- **What it is** — per-makerspace Discord alerts through an incoming webhook.
- **What it adds** — Discord as a destination in the notification matrix.
- **Without it** — no Discord surface ships at all for this space.
- **Data** — purgeable: Discord destinations and their stored webhooks (delivery logs survive).

### webhook

- **What it is** — per-makerspace **signed JSON webhooks** to systems of your own (an ERP, a Slack bot you
  wrote, a spreadsheet bridge). Not a chat room, but it sits in the same matrix: a webhook destination
  receives exactly the notification a room would, as JSON, signed with a per-destination secret.
- **What it adds** — `webhook` as a destination channel in the notification matrix, with an HTTPS endpoint
  and a signing secret per destination; `X-SpaceWorks-Signature: t=<unix>,v1=<hex>` is HMAC-SHA256 over
  `"<t>.<body>"`, plus `X-SpaceWorks-Event` and `X-SpaceWorks-Delivery` headers. Retries and the durable
  delivery log are the ones every non-email channel already has; a superadmin can re-queue failed
  deliveries from `/control/`. Verification recipe: `docs/api-client-protocol.md` → "Outbound webhooks".
- **Without it** — no signed-webhook surface ships for this space. The inbound API-client protocol is
  unaffected; other systems poll instead of being told.
- **Data** — purgeable: webhook destinations with their endpoint URLs and signing secrets (delivery logs
  survive). Endpoint URLs are validated against private and loopback ranges when saved and re-resolved at
  send time, like every other webhook channel.

---

## Reports

### reports

- **What it is** — analytics, the report registry and CSV/XLSX exports.
- **What it adds** — the `analytics` and `report_export` workflows: a server-provided report catalog,
  dashboards, accessible charts with table fallbacks, the ledger, problem reports and every registered
  report. The catalog covers every module either with a substantive report or an explicitly gated row in
  a composite operational-health report. Every CSV/XLSX export carries provenance (who generated it,
  when, for which makerspace, which report version and filters) as the first CSV line or a `Provenance`
  sheet, and staff can schedule a report to be delivered daily, weekly or monthly to a notification
  destination or a list of email recipients as a short-lived signed download link.
  Counts-only membership cohorts and recurring-plan MRR/ARR use local months and require
  `membership`; MRR requires `VIEW_FINANCE`. Server report views save filters and columns,
  with manager-authorized sharing. Schedules can require non-empty rows or a metric
  threshold, and role/action recipients resolve current authority at send time.
- **Without it** — no analytics screens, no exports and no scheduled deliveries from the console. It is a **standalone area
  rather than part of Inventory** on purpose: switching Inventory off would otherwise take the machine
  and event reports with it.
- **Data** — closed historical buckets are stored as append-only, non-PII metric rollups; corrections add
  a revision rather than rewriting history. Automatic evidence retention must finalize its rollup fence
  first, so it cannot change historical figures. Whole-tenant purge removes the rollups through tenant
  ownership, and an explicit source-module purge removes that module's derived rollups too. Purging
  `reports` deletes saved report views, schedules and their delivered files (private objects);
  other staff-list preferences and the rollups stay.

---

## Payments

### payments

**Opt-in.** It was on by default until charge *tracking* moved out from under it: a space that takes
cash needs none of this module and still keeps a full ledger of what members owe.

- **What it is** — taking money **online**, through Stripe or Razorpay behind one provider seam.
- **What it adds** — the online rail: checkout, Connect, webhooks, refunds (full or partial, through
  the same provider seam, as ledger lines that never edit the charge) and (with `mobile`) the in-app
  payment sheet. With `payments.loans` on, a loan deposit and a capped late fee can be collected
  online too.
- **Without it** — money owed is still tracked, listed and reported: the `charges.*` features raise
  the charge, members see what they owe, and staff settle it in person and record how (cash, UPI,
  bank transfer, card machine, cheque) in the append-only manual-settlement ledger. What disappears
  is only the ability to pay by card online.
- **Tracking and checkout are separate.** `charges.enabled` plus `charges.<domain>` records priced
  debts without this module or gateway credentials. Online checkout additionally requires this module,
  `payments.enabled`, the matching `payments.<domain>` feature and valid provider credentials.
- **Data** — **payments are never purged by a module purge.** A charge is the record of money that really
  changed hands, so receipts stay readable and a pending charge stays payable, waivable and markable
  paid, keeping the description it was raised under. Only purging the whole makerspace removes them.

---

## Mobile apps

### mobile

Requires `member_accounts`.

- **What it is** — the native-app substrate: attested device sessions, native push and the in-app
  payment sheet.
- **What it adds** — device registration and revocation, push delivery (feature `mobile.push`), and
  PaymentSheet when `payments` is also on.
  Canonical push uses per-device children beneath an envelope delivery, independently of inbox
  creation or the inbox module. Current source-tied member/requester accounts qualify under
  recipient policy; device registration still requires active native local selection. Staff
  use separate staff accounts with password, MFA, attestation and a fixed tenant; phone/social/OIDC
  native login is member-only and platform grants are forbidden. Matrix/personal policy and
  current source/device checks apply. See [notification-inbox.md](notification-inbox.md).
- **Without it** — native apps cannot hold a session for this space; the web app is unaffected.
- **Data** — `purge_module_data` reports it stores no data of its own to purge separately.

---

## Backup (not a module)

Public-page history participates in existing backup ownership: makerspace and event content belongs
to its tenant, while organization pages, assets, quota and creator attribution remain global.
Organization content never travels merely because a tenant is linked to it. Portable tenant imports
keep authored drafts/history and typed assets, reset publication and public disclosures, and recheck
handle collisions. Deployment restores preserve publication and IDs, then verify pointers, reference
completeness, effective schedule windows and retained-byte accounting before traffic.

### backup (retired)

**Retired in P1b (owner decision #111 Q2).** There is no `backup` module key any more; `backup/0032`
strips it from every makerspace's `enabled_modules`. Backup is a platform duty: the superadmin is
always on, every archive is encrypted to the platform key, and the superadmin backs up and restores.

- **What a Space Manager has** — a read-only "Last backup" line on the dashboard and the Backup &
  restore page (`GET makerspace/<id>/backup-status`: last covering archive and whether nightly backups
  run). For their own copy of the space's data they use **data export**.
- **What went away** — Space-Manager archive requests, listings and downloads; archive-recipient
  `age` keys, their challenges, custody states and custody alarms; the `backup` uninstall block and
  its purge plan. Makerspace archive listing, requests and downloads are superadmin-only.
- **Data** — dropping the key deleted nothing a purge would have; recipient and custody tables were
  dropped by `backup/0030`. **Archives are outside the purge guarantee**: a copy someone already
  downloaded, a deployment archive and an offsite copy are not deleted by any purge.

## Connected devices

### devices

Opt-in, no dependencies; installed only by the `full`/`everything` profiles.

- **What it is** — device identity for printers and label printers on the space's own network. A
  device is **not** a staff account: it holds an Ed25519 key, proves possession of it once at
  enrollment, and then signs every request (protocol in `docs/device-protocol.md`).
- **What it adds** — staff device enrollment, rename, offline threshold, key rotation and revocation,
  plus signed heartbeats. With `machines` and `machine_service` installed, staff holding
  `MANAGE_DEVICES` and management scope for the selected machine can bind a printer and create a
  command for its explicitly assigned in-progress request. Bounded delivery leases become durable
  ownership after acknowledgement. Measurements pass through the existing completion/failure workflow.
  Automatic application defaults off; scoped staff approval supplies the approving User. Charges use
  current machine pricing, and failed jobs create no charge. Telemetry affects staff display only.
  Every mutation leaves typed device provenance and an audit row. The server wire contract is in
  [Printer protocol](device-printer-protocol.md).
- **Without it** — device routes answer 400 and cannot enroll, authenticate or mutate. Printer routes
  additionally require both machine modules and answer 400 when either is off. Tombstoning the devices
  app removes its routes with 404.
- **Data** — `purge_module_data devices` deletes printer consumption claims, jobs, commands and
  bindings, then replay nonces, enrollments, device events and identities. Machine workflows and the
  payment ledger survive. Purging a machine adapter nulls live printer links and retains history;
  missing targets cannot deliver or finish. Tenant moves retain applied reports and source snapshots,
  disable bindings and automatic application, cancel commands, clear delivery credentials and turn
  unprocessed work into inert review. Device keys, enrollments and nonces never travel.

- **Monitoring** - both scheduler topologies check offline state once a minute. Offline/recovery
  history appears in module operational health. Device alerts have their own notification feature;
  every channel is opt-in and initially off. The Devices console exposes identity/status/enrollment
  to device managers. Printer jobs and label delivery controls arrive with their adapter lanes.

---


### sms

Opt-in and default off, independently of OTP and the optional inbox. Canonical
`ChannelConfiguration` and personal envelopes use Twilio SMS. Eligible member accounts
have a non-revoked membership or an owned loan/request, booking, event registration,
machine-service request or charge. Account-only owners qualify; revoked/restricted/deleting
accounts are excluded. Staff delivery needs a separate active local staff account and source
role authority. Current staff SMS diagnostics cannot acquire consent via member-only APIs.

SMS consent binds the verified phone instance, sender and configuration generation; phone
verification alone does not subscribe. Matrix/category/legacy opt-outs and physical STOP win.
Own credentials take precedence, including incomplete configurations which refuse delivery.
Platform notification sending needs operator and tenant opt-in, initially off. OTP uses its
separate platform number/transport; tenants may use neither OTP AccountSid nor its number.
Never share a Twilio Messaging Service between OTP and notification numbers.

Uninstall stops delivery and retains history. Channel purge removes tenant configuration/
private rows according to the purge plan after preserving retired verification. Global sender
identity/history, physical suppression/alias/correlation and provider references survive to
protect other accounts/tenants and late callbacks. Reinstall never restores old consent.
Canonical ingress commits STOP before acknowledgement even for frozen/disabled tenants.
START does not subscribe. Quotas count logical messages once; billed SMS segments remain
separate from estimates. See [channel setup](messaging-channels.md).

### whatsapp

Opt-in, default off and personal-only, with canonical Twilio or Meta providers. The module
key is registered, resolving the old Meta missing-module blocker. A current tenant-tied
member/account-only owner or authorized local staff account still needs its own signed
matching inbound endpoint proof. SMS/phone login does not establish WhatsApp consent.
Matrix/category opt-outs, source standing, physical STOP and installation generation apply.
Platform sending needs explicit operator and tenant opt-in; broken own credentials never
fall back. Existing operational installs require explicit conversion preserving enablement
and opt-outs.

Twilio uses approved Content SIDs; Meta uses WABA templates and a configured App ID, phone ID,
access token, app secret and verify token. Provider refresh owns approval; imported templates
remain needs_review. Reviewed feature/event/audience variables constrain lifecycle bodies;
canonical document-media bindings retain private short-lived grants. Authenticated inbound
opens a bounded 24-hour session window; outside it an approved template is required.

The sender/phone BSUID barrier admits one probe before verified correlation, shared across
tenants using the sender. Unmapped alias STOP blocks unknown-alias pairs; other sends defer
and skip after 72 hours without confirmation. Unknown outcomes and expired addressed leases
are held without blind resend. Explicit re-consent may reset blocked pairs; START cannot.

Uninstall retains history. Purge removes tenant configuration/private data only after preserving
retired verifiers; shared suppression/alias/correlation, sender history and provider references
survive. Member consent/connection surfaces remain independent of inbox installation.
Provisioning and exact callbacks: [channel guide](messaging-channels.md). Destructive integrations
0043 retirement and sending activation remain held pending [replay sign-off](notification-reconciliation-rollout.md).
