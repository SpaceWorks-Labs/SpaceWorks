# Space Works documentation

Every guide in this repository, grouped by what you are trying to do. New here? Start with the
five-minute quickstart below; everything after it is reference material for when you need it.

## Quickstart (about five minutes)

1. On a 64-bit Linux server (Ubuntu 24.04 is the tested target) or a Mac with Docker Desktop, run:

   ```sh
   curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh
   ```

   Quick setup asks for the web address, your makerspace's name, the areas you run and your email.
   Press Enter to accept each suggested answer; nothing changes until you confirm the summary.
2. Open the address the installer prints (for a local trial, `http://localhost/admin`).
3. Sign in with the admin account the installer created. Its generated password is saved in
   `/opt/spaceworks/.spaceworks-bootstrap-credential.json`; you choose your own password and set up
   two-step sign-in at first sign-in.
4. Follow the guided setup on the dashboard: name, logo, opening hours, the areas you run and staff
   invitations. Every step can be skipped and resumed, and the "Next steps" card shows what is left.

The install log is `/opt/spaceworks/install.log`. To update, run the same command again.

**Going further:** your own domain and HTTPS, an API-only server, external storage, cloud providers
and hosting other makerspaces are covered in [Install and update](install-and-update.md),
[Choose your hosting](choose-your-hosting.md) and the [Self-hosting guide](self-hosting.md).

## Getting started

- [Setting up Space Works](setup-for-makerspaces.md) — plain-language setup walkthrough for organisers who are not developers.
- [Choose your hosting](choose-your-hosting.md) — every way to run Space Works compared, self-host first: full VPS, API on your server with the website elsewhere, static website, cloud providers, the free profile and hosting other makerspaces.
- [Install and update](install-and-update.md) — the one-line installer, every setup question, forks, automatic deploys and Windows support.
- [Features](FEATURES.md) — everything Space Works runs today, area by area.
- [0.12.0 release notes](release-0.12.0.md), [upgrade guide](upgrade-to-0.12.0.md) and [security verification](security-summary-0.12.0.md) — changes, update steps and the completed versus pending checks. The unpublished 0.11.0 candidate's [notes](release-0.11.0.md), [upgrade guide](upgrade-to-0.11.0.md) and [security summary](security-summary-0.11.0.md) are kept as history; their changes ship in 0.12.0.
- [Hosting and roles](README-HOSTING.md) — roles and staff accounts, first-run access, split deployments and moving a space to its own server.
- [Roadmap and further work](future-work.md) — current focus and further work.
- [Landing-page feature inventory](LANDING-PAGE-FEATURES.md) — the full product description used for the public site.
- [Landing-page positioning](LANDING-PAGE-POSITIONING.md) — optional modules compared for the public site.

## Running a space

- [Task manuals](USER-MANUALS.md) — normal workflows grouped by role and screen.
- [Module and feature switch-off reference](MODULES-OFF.md) — navigation, new actions, retained history and existing obligations when an area is disabled.
- [Logging and audit](logging-and-audit.md) — correlation, safe metadata and the [audit action reference](audit-action-reference.md).

- [Sign-in, identity and borrowing](sign-in-and-borrowing.md) — sign-in methods, running without member accounts, who may borrow, login-method switches.
- [Notification channels, rooms and recipients](notification-routing.md) — chat rooms, who hears about what, and editing message wording.
- [Loan policy, renewal and reminders](loan-policy.md) — loan limits, renewals and reminder settings.
- [Machine training and maintenance reminders](machine-training-maintenance.md) — training types, certifications and maintenance schedules.
- [Membership admission](membership-admission.md) — join requests, vouching and application forms.
- [Member accounts and renewal automation](member-account-renewals.md) — membership plans and automatic renewals.
- [Member and finance delegation](RBAC-MEMBERS-FINANCE.md) — which actions cover members and money.
- [Core billing](payment-billing.md) — due dates, reminders and manual refunds without online payments.
- [Receipt documents and finance exports](payment-documents.md) — receipts, credit notes and finance exports.
- [Space packs](SPACE-PACKS.md) — copy configuration between spaces with packs and saved install profiles.
- [Kiosk offline continuity](KIOSK-OFFLINE.md) — how scanner Stations keep working offline.
- [Failed kiosk replay recovery](KIOSK-RECOVERY.md) — reviewing kiosk handovers that failed to replay.
- [Personal notifications and delivery controls](notification-inbox.md) — the member inbox and personal delivery settings.
- [SMS and WhatsApp notifications](messaging-channels.md) — Twilio SMS and Twilio/Meta WhatsApp delivery.
- [Notifications and bookings (WP3)](WP3-NOTIFICATIONS-BOOKINGS.md) — payment-failure and booking notification behaviour.
- [Inventory and machine operations (WP4)](WP4-INVENTORY.md) — opt-in inventory and machine operation features.
- [Account deletion privacy note](privacy-account-deletion.md) — member account deletion, archive, restore and purge.
- [Google Sheets import privacy note](privacy-sheet-import.md) — what SpaceWorks reads when staff import from a public sheet.

### Events programmes

- [Events programme guide](events/README.md) — enabled-area setup and where each runbook fits.
- [Integration status](events/integration-status.md) — current feature gates and the dated integration evidence ledger.
- [Organizer runbook](events/organizer.md) — review, RSVP, results and certificates.
- [Participant runbook](events/participant.md) — apply, form a team and submit files or links.
- [Mentor runbook](events/mentor.md) — Mentor Desk, office hours and rounds.
- [Volunteer runbook](events/volunteer.md) — apply for shifts and verify volunteer work.
- [Judge and sponsor runbook](events/judge.md) — judge frozen projects or review sponsor-track submissions.
- [Events operator setup](events/operations.md) — migrations, credential/account keys, online scanner, optional ClamAV and ffprobe.
- [Uploads and retention](events/media.md) — managed 25 GB and self-host budgets, media limits and file expiry.
- [Event reimbursements](events/reimbursement.md) and [reimbursement operations](events/reimbursement-operations.md) — optional travel-support budgets, awards, claims and recorded payouts.
- [Staged event forms](events/staged-forms.md) — revision-pinned participant forms, deadlines and completion requirements.
- [Owner add-on traceability](events/acceptance.md) — code, test and route evidence for each add-on.
- [Events artwork inventory](events-programme-artwork-inventory.md) — the themed certificate, badge and illustration artwork.

## Modules

- [MODULES.md](MODULES.md) — every module key: what it is, what it adds, what happens without it, what a purge deletes.
- [Choosing modules](choosing-modules.md) — areas, the full module and feature tables, install, uninstall, purge and tombstoning.
- [Inventory and Stocktake modules](MODULES-INVENTORY.md) — module reference continued for those areas.
- [Machines, Events, Bookings and Membership modules](MODULES-WORKSHOPS.md) — module reference continued for those areas.
- [Notifications, Reports, Payments, Mobile and Devices modules](MODULES-PLATFORM.md) — module reference continued for those areas.
- [Editions and module lifecycle](MODULES-LIFECYCLE.md) — `SPACEWORKS_EDITION` and how modules install and retire.

## Operations and security

- [Self-hosting guide](self-hosting.md) — production Compose, HTTPS, the control plane, environment, storage and backups.
- [Advanced configuration](../.github/ADVANCED.md) — Telegram, chat rooms, HMAC clients, hardening, managed Postgres and scheduled reminders.
- [Production deployment](deploy-production.md) — choosing a hosting contract and deploying it.
- [Hosting other makerspaces](self-hosting.md#plans-and-hosting-other-makerspaces-optional) — the optional plans and hosting section (deploy-saas.md is a pointer).
- [Hosting overview](deploy/cloud-overview.md) — operational contracts to choose before a cloud provider.
- [Cloud contracts](deploy/cloud-contracts.md), [managed environment](deploy/cloud-environment.md) and [managed recovery](deploy/cloud-recovery.md) — the shared rules every cloud recipe follows.
- Cloud recipes: [Cloud Run](deploy/cloud-cloud-run.md), [DigitalOcean](deploy/cloud-digitalocean.md), [Docker](deploy/cloud-docker.md), [Fly.io](deploy/cloud-fly.md), [Koyeb](deploy/cloud-koyeb.md), [Kubernetes](deploy/cloud-kubernetes.md), [Railway](deploy/cloud-railway.md), [Render](deploy/cloud-render.md), [free managed stack](deploy/cloud-free.md), [Oracle Always Free](deploy/cloud-oracle-free.md) and [static frontends](deploy/cloud-static.md).
- [Helm deployment](helm.md) — the Kubernetes chart in `charts/spaceworks`.
- [Supabase PostgreSQL](supabase-deployment.md) — using Supabase as the database.
- [Single-tenant branded frontend](single-tenant-frontend.md) — running the frontend for one makerspace.
- [Your own domain or frontend](own-domain-and-frontend.md) — a space's own domain (DNS proof first), hiding it from the platform, and embeds, API clients and webhooks.
- [Database recovery after an update](update-recovery.md) — restoring dumps and inspecting failed deployments.
- [Account portability](account-portability.md) — what travels when a space is backed up, restored or moved to another deployment: people, staff roles and credentials.
- [Environment reference](environment-reference.md), [delivery settings](environment-reference-delivery.md) and [operations settings](environment-operations.md) — every environment variable.
- [Monitoring and private web analytics](monitoring-and-analytics.md) — storage, metrics and analytics; [web telemetry providers](web-telemetry-providers.md), [Metabase setup](metabase-setup.md) and [Grafana setup](grafana-setup.md).
- [Apple and Google Wallet passes](wallet-passes.md) — what holders get, how to obtain and paste credentials, how to verify offline, revocation and troubleshooting.
- [Platform monitoring and tenant usage](platform-monitoring.md) — the superadmin platform dashboard.
- [Scoped PII encryption](scoped-pii-encryption.md) — the opt-in personal-data encryption runbook.
- [Notification reconciliation checkpoints](notification-reconciliation-rollout.md) — the held sending-activation rollout.
- [Security policy](../.github/SECURITY.md) — how to report a vulnerability.
- [Dependency security alerts](security/dependency-alerts-r1.md) — every open alert and its resolution.
- [Module-architecture security review](module-program-security-report.md) — the security and loophole review of the module programme.
- [Printing kernel cutover](printing-kernel-b4-cutover.md) — historical record of the finished cutover.

## Development

- [Development](../.github/DEVELOPMENT.md) — run the backend and frontend from source.
- [Contributing](../.github/CONTRIBUTING.md) — conventions, branches and pull requests.
- [Architecture](../ARCHITECTURE.md) — topology, tenancy, identity, domain modules and data flows.
- [Dev workflow](DEV-WORKFLOW.md) — program state, worktrees, the test harness and the dev stack.
- [Project status](PROJECT-STATUS.md) — what exists today.
- [Project history](PROJECT-HISTORY.md) — the condensed changelog, newest first.
- [Changelog](../CHANGELOG.md) — release notes.
- [Brand v1](brand/README.md) — logo masters, colour, type and spacing.
- [Product](../PRODUCT.md) — users, purpose, brand personality and design principles.
- [Mobile apps PRD](mobile/MOBILE-APP-PRD.md) — the Android and iOS app requirements.

## Reference

- [Invariants](INVARIANTS.md) — the load-bearing rules, read per area before changing code.
- [Source map](SOURCE-MAP.md) — what each backend app and frontend directory owns, continued in
  [apps](SOURCE-MAP-APPS.md), [client](SOURCE-MAP-CLIENT.md), [community](SOURCE-MAP-COMMUNITY.md),
  [consoles](SOURCE-MAP-CONSOLES.md), [domains](SOURCE-MAP-DOMAINS.md),
  [events programme](SOURCE-MAP-EVENTS-PROGRAMME.md), [module families](SOURCE-MAP-MODULE-FAMILIES.md),
  [notifications](SOURCE-MAP-NOTIFICATIONS.md), [platform](SOURCE-MAP-PLATFORM.md),
  [recovery](SOURCE-MAP-RECOVERY.md), [booking passes](SOURCE-MAP-BOOKING-PASSES.md),
  [booking reads](SOURCE-MAP-BOOKING-READS.md) and [booking websites](SOURCE-MAP-BOOKING-WEBSITES.md).
- [API guide](api-guide.md) — start here: clients, scopes, signing in Python/JS/curl, tokens, OAuth apps, pagination, errors, limits, versioning.
- [API client protocol](api-client-protocol.md) — scoped, signed clients for the protected API.
- [Signed webhook v2](webhooks-v2.md) — payload format 2 and its [JSON schema](webhooks-v2.schema.json).
- [Device protocol](device-protocol.md) — enrollment and signed requests for printers and label printers.
- [Printer delivery and reports](device-printer-protocol.md) — printer job delivery and measured terminal reports.
- [Label commands](device-label-commands.md) — sending QR print batches to label printers.
- [Mobile integration](mobile-integration.md) — connecting branded Android and iOS apps.
- [Notifications v2 contract](notification-contract.md) — the personal delivery contract and its integration limits.
- [Notification coverage](notification-coverage.md) — the complete notification trigger inventory.
- [Reminder schedules](reminder-schedules.md) — the shared reminder sweeper.
- [Reports and measurement notes](SOURCE-MAP-REPORTS.md) — the report registry, output allowlist and the
  measurement rules of every report family.
