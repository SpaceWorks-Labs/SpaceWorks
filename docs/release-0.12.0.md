# SpaceWorks 0.12.0

SpaceWorks 0.12.0 connects inventory, events, bookings, repairs, reports and the Shop, and includes everything prepared for the unpublished 0.11.0 candidate. The 0.11.0 candidate was never published; its [notes](release-0.11.0.md) remain as history and their changes are part of this release.

## Included from the 0.11.0 candidate

A separate Inventory page and makerspace overview, light mode by default, delegated public-stat settings, account-owned histories, the Technician and Shop Manager roles, configurable events and hackathons, member cards and certificates, the Shop, the language switcher and help centre, platform administration and the standard backend/frontend images. See the [0.11.0 candidate notes](release-0.11.0.md) and the [changelog](../CHANGELOG.md) for detail.

## For members and makerspaces

- An equipment request can name its purpose: your own event registration, your own exact booking, both or neither. The purpose explains the request; it does not approve it or issue equipment. See [equipment kits and contextual requests](equipment-kits.md).
- You can request a published **kit** instead of picking items one by one. Returnable items follow the usual loan, evidence and return workflow; kit consumables become a plan and use no stock until staff record actual use.
- Refusals for membership eligibility and delegated access now say what is wrong and what to do next. The server still makes every decision.
- A private booking calendar link stays tied to the account that fetched it, so switching accounts cannot show another person's link.

## For staff and event organisers

- Staff can add, change or remove an event or booking **context** on an existing loan or direct handout. Each change rechecks authority on the old and new records and grants no new access. See [equipment loan context](equipment-contexts.md).
- Inventory staff create, version, publish and archive kits. Event and booking staff can propose equipment for a person on their authorized registration or booking; inventory staff keep the review and handover actions.
- An event can be linked to a room **booking** that owns the single room charge. Event registration charges and the room charge stay independent, free or paid in any combination. Linking is refused while an event venue fee is configured or has history. A rejected or cancelled booking can be replaced once by a new booking; the original keeps its price, payment, receipts and audit.
- Staff booking creation shows a **price confirmation** bound to the room, member, window and charge mode. If the price changed since the preview, the create is refused with `price_changed` before anything is written.
- **Booking readiness** shows, before submit, what admission would refuse (room outage, machine under repair, certification) using the same admission checks, plus advisory warnings.
- Queue estimates apply the maintenance lockout rule, including usage meters and per-type grace, so a machine blocked by overdue maintenance no longer looks available.
- With repairs enabled, an area manager can open one repair issue from a **damaged return** line and see a loan's repair context.
- **Related facts** show registration, attendance, booking arrival, presence counts and machine sessions side by side, each from its own source and only where the viewer's module and authority allow. **Event linked finance** shows registration charges, venue fee, the Booking-owned room charge, reimbursements, payouts and budget per currency without summing across currencies.
- Loan-context reports, loan timelines and per-activity consumable reports count each request once in exactly one context. See [equipment reports](equipment-reports.md).
- Shop staff can move an order to makerspace pickup through an audited action. Sales of variants linked to an inventory consumable record their consumable cost exactly once. An order cancellation defect is fixed.
- Event co-organizers can invite volunteers, mentors, judges and sponsor representatives with that helper role's permissions.

## Also new in 0.12.0

- **Guest passes.** A dated permit for someone who is not a member: sponsored by a member, issued by staff, linked to an event registration, or bought as a paid day pass. A pass is never a membership. The Space Manager chooses what it unlocks (nothing, on-site only, or borrowing with a deposit). See `membership.guest_passes` in [the module reference](MODULES.md).
- **Organization hours bank.** Organizations get an hours allowance per space; their bookings use those hours before any charge, and a cancelled booking returns them.
- **Donations and sponsors for non-profits**, with a new **Fundraising** role that sees only donation money. See [donations and sponsors](MODULES.md#donations-and-sponsors-finance-release-2).
- **Each role sees what it manages.** Area managers get grouped views of their own finance, To-Buy, consumables, repairs and warranties; the Space Manager sees all areas together, grouped by area.
- **One self-hosted mode.** Hosting other makerspaces is an optional switch for the platform owner. Spaces are unlimited by default; a hosted space can have a plan, limits and rates.
- **Hybrid setup.** Keep the database, Redis, file storage, email and website on this server or move any of them elsewhere (for example Supabase for the database, Cloudflare R2 for files). See [hybrid setup](install-and-update.md#hybrid-setup-outside-database-redis-storage-and-email).
- **A standard installer.** `curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh`. Releases carry checksums and a keyless signature. See [install and update](install-and-update.md).
- **Grafana beside Metabase** for per-space and platform analytics, each reading only its own curated, read-only data. See [Grafana setup](grafana-setup.md) and [Metabase setup](metabase-setup.md).
- **Money at full precision**, including three-decimal currencies (KWD, BHD, OMR, JOD, TND). A member who is restricted over an unpaid charge can still pay it. See [payments and billing](payment-billing.md).
- **A safer base image.** The backend image is built on Ubuntu 24.04 LTS by default, with Debian options for source builds. See [self-hosting](self-hosting.md).
- **Inventory, not Lending.** The area is called Inventory everywhere you read it, and it can be switched off per space like any other area. Dark mode is now true black.

## For operators

- Direct-room notification delivery fails closed when its lookup errors: nothing is sent and no quota is spent, while independent email delivery remains eligible.
- The web telemetry settings endpoint requires a signed-in active account with no pending password change. Revoking a person's authentication now also ends their personal access tokens and disconnects their OAuth app connections.
- Linked mutations (event/booking loan context, the loan repair handoff and the Shop pickup move) are session-only; their reads remain available to API bearer clients. The event booking link is session-only for reads and writes.
- The API schema advertises version 0.12.0 with 1,974 paths. See the [upgrade guide](upgrade-to-0.12.0.md) for the new migrations, including one non-atomic concurrent index build, and the [security verification summary](security-summary-0.12.0.md) for completed and pending checks.

## Verification status

This is release documentation for a build that has not finished its release gates. The complete backend regression, the browser/role/module/money matrix, PostgreSQL scenarios for the new connections, deployment and old-version upgrade rehearsals, a proven 0.9.2 rollback and exact final-image checks are still pending. Earlier passing results for the 0.11.0 candidate do not establish that this release is green. The sample limits and physical-printer limits recorded in the [0.11.0 candidate notes](release-0.11.0.md#verification-and-accepted-sample-limits) still apply.
