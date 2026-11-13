# SpaceWorks 0.12.0

SpaceWorks 0.12.0 connects inventory, events, bookings, repairs, reports and the Shop, and includes everything prepared for the unpublished 0.11.0 candidate. The 0.11.0 candidate was never published; its [notes](release-0.11.0.md) remain as history and their changes are part of this release.

## Included from the 0.11.0 candidate

A separate Inventory page and makerspace overview, light mode by default, delegated public-stat settings, account-owned histories, the Technician and Shop Manager roles, configurable events and hackathons, member cards and certificates, the Shop, the language switcher and help centre, platform administration and the standard backend/frontend images. See the [0.11.0 candidate notes](release-0.11.0.md) and the [changelog](../CHANGELOG.md) for detail.

## What's new in 0.12.0, by area

### The website and the front page

- **A scrolling product page** opens every site's front page: a pinned opening scene, a sample loan told step by step, then areas, how it works, self-hosting, the licence, the apps, the docs and common questions. The earlier "Find a space near you" section is gone from the page; the **Spaces** link in the header and the `/spaces` page stay. It becomes a plain static page for visitors who prefer reduced motion and on narrow screens, and has a calm dark theme. See [the front page guide](how-to/front-page-and-features.md).
- **A Features page** (`/features`) lists every area, module and feature switch, with its default and a link to the docs, and each module has its own page under `/features/<module>` with its features, reports, analytics, limits and integrations. It is built from the app's own catalogue, so it cannot drift from the software. A section shows the ID card and badge designer.
- **Official links.** The page links to the main repository and to the public Android and iOS app repositories; the native Android and iOS apps are shown as released. They are distributed through GitHub Releases only: each app row says **Download from GitHub Releases** and links to that repository's latest release. There are no store buttons.
- **A front-page switch.** `HUB_LANDING_ENABLED` is on by default on every install. Setup asks "Show the SpaceWorks product page at your site's front page?", and `bash scripts/apply-settings.sh --landing on|off` changes it later. With it off, `/` opens the space (or the spaces directory when there are several); docs, spaces, about and features keep working.
- **A sample ID card on the sign-in screens** (wide screens only, decorative) shows what the card designer produces.

### Members and profiles

- **One global profile per account**, visible to signed-in members of every space by default, with a separate, consent-based switch for the open web. It carries a status, about, experience, education, volunteering, skills, links, projects (including a hackathon submission imported as a project), spaces and organizations, "vouched by", verified and self-reported achievements, and an optional activity graph with GitHub. Private events, unpublished results and contact details are never shown. Earlier per-space profiles are merged into it and kept read-only. See [the profile guide](how-to/member-profile.md).
- **A username for everyone.** Sign-up asks for one with a live availability check and a suggestion, social sign-in gets a "change it?" step, and older accounts see a blocking "Choose your username" step. Reserved names are refused. See [Usernames](how-to/usernames.md).
- **A one-time notice** tells members whose profile was never hidden that it is now visible on the platform, with a link to their settings.

### Cards, badges and certificates

- **Card Studio.** One designer and one print engine for member cards, staff ID cards, event badges, tickets and event certificates. Quick mode for a fast start, Advanced for the full canvas: rich text, colour, gradient or uploaded picture backgrounds, canvas placement with guides and snapping, a layers panel, and sample people to check long names. Built-in looks come in light and dark, and a space can save, rename, duplicate, export and import its own templates (limit `card_templates`, none by default). See [Design cards and certificates](how-to/design-cards-and-certificates.md).
- **More designer tools.** Millimetre rulers with guide lines, side-by-side **compare** of two saved versions (front and back, with the list of changed layers), a **print-ready PDF** with bleed and crop marks (and a 300 dpi PNG with bleed), and barcodes in Code 128, Code 39, EAN-13, UPC-A, PDF417, Data Matrix and Aztec, drawn identically in the browser and on the server. A CSV merge previews the published design, the same as the PDF.
- **Staff cards** are designed and printed like member cards.
- **Bulk photo upload.** Choose photos or a zip and they are matched to cards by file name (card number, then the part of the email before the `@`, then the full name), reviewed in a table and applied. See [Remove card photo backgrounds](how-to/background-eraser.md).
- **Background eraser.** An optional cut-out of the holder's photo, done by a service the space runs itself: any HTTPS service that implements the signed [Image Adapter API](image-adapters/README.md) (`POST /v1/remove-background`). SpaceWorks bundles no eraser and sends nothing to a third party. The switch `cards.photo_cutout` is off by default. Where it is on, members see a notice that card photos may be sent to the space's removal service and can opt out; their original photo is then used, and staff and bulk runs skip them. Member-card photos are limited to 8 MB, and an uploaded photo is re-encoded with its location data removed.
- **Certificates on the same engine.** Event certificates can use the signature, signature row, seal, number and verification QR layers and three built-in looks. `CERTIFICATE_SHARED_RENDERER` is off by default and is pinned per certificate, so issued certificates never change. Designs that saved before still print as before.

### The public space page and display screens

- A space's public page can show **Here now**, **Machines now** and an **events calendar**, each only while its area is on. Names appear only for people whose profile and presence settings allow it; everyone else is counted. Machines now never says who is using a machine.
- **Display screens** run those panels and an announcement full-screen on a TV. A screen shows a pairing code, staff pair it under **Settings, Display screens**, and changes reach it within about ten seconds. It keeps its last data if the network drops. A Space Manager chooses which panels each screen and the public page show, in what order and layout: Here now, Machines now, events calendar, announcement, public stats, opening hours, inventory highlights and a sponsors or logo wall. Paired screens have a limit that has no cap unless the platform operator sets one. See [the display guide](how-to/display-screens.md).

- **Anthias and screens without a code.** A player that cannot type a pairing code (for example [Anthias](how-to/anthias.md) on a Raspberry Pi) uses a screen link instead. The secret travels in an `Authorization` header, not in the address, so it stays out of access logs; link screens need no sign-in, set no cookies and are kept out of analytics. SpaceWorks can also add the pages as assets to a player's Anthias server. A player on a private network address is allowed by default on a self-hosted install and refused by default on a hosted edition.

### Staff

- **Staff management is explained end to end**: one account with roles per space, several roles at once, machine reach by type or by machine, email invitations, what revoking does and staff ID cards. See [Give someone a role](how-to/roles-and-handover.md).

### Machines

- **Machine access replaces certifications.** There are no certifications or inductions. The Space Manager (or a Machine Manager for their machines) grants machine access to whichever members they choose, per machine or per machine type, with an optional end date, or marks a machine open to all members. A refusal says `no_machine_access` or `machine_access_expired`. On upgrade, members who held the required certifications keep access as grants, ungated machines become open to all members, and nothing is deleted. See [Give members machine access](how-to/machine-access.md).
- **Device Adapter API.** A signed, vendor-neutral contract for bridges that run next to hardware: status, controls, job dispatch, access decisions for doors and machines, NFC and PIN credentials, shelf-pointer calibration and kiosk self-checkout. Everything is off until `machines.integrations` and the child switches are on. Media and data: camera watch with listen-only audio by default and staff push-to-talk, saved timelapses, thumbnails and previews, detection alerts, telemetry charts, diagnostics, a signed offline access list for doors, configuration push and signed time. **Automation is not in SpaceWorks**: it stores, shows and notifies, and the adapter decides what to do. Staff use the **Device adapters** screen. See [Manage device adapters](how-to/adapter-console.md) and the [API](device-adapters/README.md).
- **One Machine service for every machine type.** The separate Printing module is retired: the 3D print queue is a machine type inside Machine service, next to lasers, CNC and cutters. Spaces that had printing on keep Machine service on; see the [upgrade note](upgrade-to-0.12.0.md#review-changed-behavior-and-settings).
- **Consumables per machine type, and one "Add a machine type" setup.** Each machine type lists what it uses up, in its own units: filament in grams, resin in millilitres, sheets or area for a laser, boards and bits for a PCB mill, metres of vinyl, thousands of stitches. Each consumable says whether a job needs it, who estimates it, who records the actual (staff, the member or a machine adapter), an optional price per unit and the stock it draws from, with the existing low-stock alerts. Each type also carries booking defaults for its bookable spaces, its notification routing, and training notes and files members see before using it. A step-by-step setup prefilled from templates (FDM, resin, laser, PCB mill, CNC, vinyl, embroidery, sewing, soldering, kiln, generic time-based, or blank) creates any machine type. On upgrade, existing per-machine consumables and material catalogues become profile rows with no price of their own, so no job is charged differently. See [Machine consumables](how-to/machine-consumables.md).
- **Shelf pointer.** Staff can calibrate a laser or LED pointer, press **Show on shelf** on an item, box or issue line, be guided through a stocktake shelf by shelf, and record **shelf checks**. Staff-only; positions never reach the public. SpaceWorks ships no hardware: a [Raspberry Pi or ESP32 adapter guide](device-adapters/hardware/shelf-pointer.md) says what such an adapter must do over the Device Adapter API. Laser power and on-time are capped by the server. See [Use a shelf pointer](how-to/shelf-pointer.md).
- **Printing foundation.** Print requests and the machine job workflow, label printers for QR batches and enrolled printers that pull jobs and report back. See [Machine printing](how-to/machine-printing.md).
- **Machine use logged with an event.** "This is for an event" on machine sessions and service requests (no switch), set or cleared by the area manager, shown on the event page and in two reports, with an organiser's record of approval to charge a cost to the event. See [Log machine use for an event](how-to/machine-use-for-events.md).

### Organizations, events and notifications

- **Organization workspaces** let a club or society run Events, Memberships and Bookings without a makerspace, with member **units** for chapters and districts, and one card for space and organization. See [Organizations](modules/organizations.md).
- **Event badges** have a designer, role variants and desk printing; the **hackathon flow** covers staged review, judging, prizes and People's choice. **Prize money is recorded by a person, never sent automatically**, and prize tax is a record only. See [Events](modules/events.md).
- **Notifications** are delivered by the background worker (every outbound email, SMS, WhatsApp, push, chat and Telegram message goes through it), and a new in-app notice marks the profile change.
- **Limits default to none, per module.** Every module that creates something countable has its own limits (requests, transfers, stocktakes, claims, public-page images, scheduled reports, adapter media and telemetry, display players, cards, and the rest); four modules have none and say why. The platform operator can set a **platform default** for any limit and override it per space; a space's own value wins, then a hosted plan, then the default, then unlimited. Staff see a warning from **80%**, and at **100%** only *new* items are refused, with a clear message; existing data is never touched. Space Managers and the superadmin get one notice per crossing. Space Managers see **Limits and usage** by module, read-only. See [Plans and limits](self-hosting.md#plans-and-limits).

### Reports, module screens and colours

- **A Reports hub** groups every report by the same module groups as the module screens, with search and pins, and shows each role only the reports for actions it holds. A module that is switched off hides its reports. Each module also links to its hub group, and the platform operator sees roll-ups across spaces. Reports reach Metabase and Grafana through the curated views.
- **Module and feature screens** (Space Manager settings and the platform screen) are grouped by area and role, with search, a clear on, off, locked-by-platform or needs-parent state with the reason, what each switch affects and bulk area switches with a confirmation. Every switch is audited.
- **Colour settings** per space with live previews per surface (staff console, member app, public pages, cards and certificates, display screens), light and solid-black dark, contrast checks with suggested fixes, presets and reset.

### Look and feel

- **One loading animation.** The Space Works box opening replaces spinners and placeholders in pages, panels, dialogs and buttons, and the first load shows the box unfolding into the header logo. With reduced motion you get the still logo.
- **Motion.** Moving between pages cross-fades while the side bar and top bar stay still, the active side bar item slides, and menus, dialogs, drawers and toasts share one set of short durations. Reduced motion turns all of it off.
- **Dark mode** is one solid black family everywhere, and the front page scrolls as one product page (see above).

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
- **Booking readiness** shows, before submit, what admission would refuse (room outage, machine under repair, machine access) using the same admission checks, plus advisory warnings.
- Queue estimates apply the maintenance lockout rule, including usage meters and per-type grace, so a machine blocked by overdue maintenance no longer looks available.
- With repairs enabled, an area manager can open one repair issue from a **damaged return** line and see a loan's repair context.
- **Related facts** show registration, attendance, booking arrival, presence counts and machine sessions side by side, each from its own source and only where the viewer's module and authority allow. **Event linked finance** shows registration charges, venue fee, the Booking-owned room charge, reimbursements, payouts and budget per currency without summing across currencies.
- Loan-context reports, loan timelines and per-activity consumable reports count each request once in exactly one context. See [equipment reports](equipment-reports.md).
- Shop staff can move an order to makerspace pickup through an audited action. Sales of variants linked to an inventory consumable record their consumable cost exactly once. An order cancellation defect is fixed.
- Event co-organizers can invite volunteers, mentors, judges and sponsor representatives with that helper role's permissions.

## Also new in 0.12.0

- **Guest passes.** A dated permit for someone who is not a member: sponsored by a member, issued by staff, linked to an event registration, or bought as a paid day pass. A pass is never a membership. The Space Manager chooses what it unlocks (nothing, on-site only, or borrowing with a deposit). See `membership.guest_passes` in [the module reference](MODULES.md).
- **Organization hours bank.** Organizations get an hours allowance per space; their bookings use those hours before any charge, and a cancelled booking returns them.
- **Donations and sponsors for non-profits**, with a new **Fundraising** role that sees only donation money. See [donations and sponsors](MODULES.md#donations-and-sponsors-finance).
- **Each role sees what it manages.** Area managers get grouped views of their own finance, To-Buy, consumables, repairs and warranties; the Space Manager sees all areas together, grouped by area.
- **One self-hosted mode.** Hosting other makerspaces is an optional switch for the platform owner. Spaces are unlimited by default; a hosted space can have a plan, limits and rates.
- **Hybrid setup.** Keep the database, Redis, file storage, email and website on this server or move any of them elsewhere (for example Supabase for the database, Cloudflare R2 for files). See [hybrid setup](install-and-update.md#hybrid-setup-outside-database-redis-storage-and-email).
- **A standard installer.** `curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh`. Releases carry checksums and a keyless signature. See [install and update](install-and-update.md).
- **Grafana beside Metabase** for per-space and platform analytics, each reading only its own curated, read-only data. See [Grafana setup](grafana-setup.md) and [Metabase setup](metabase-setup.md).
- **Money at full precision**, including three-decimal currencies (KWD, BHD, OMR, JOD, TND). A member who is restricted over an unpaid charge can still pay it. See [payments and billing](payment-billing.md).
- **A safer base image.** The backend image is built on Ubuntu 24.04 LTS by default, with Debian options for source builds. See [self-hosting](self-hosting.md).
- **Inventory, not Lending.** The area is called Inventory everywhere you read it, and it can be switched off per space like any other area.

## Security, resilience and sign-in

- **Security review fixes.** An independent review of the 0.12.0 work found no critical issues. Every finding, high to low, is fixed: profile and directory privacy and the protection of minors; protection against server-side request forgery on Anthias, webhook and image-adapter calls (the connection is pinned to the checked address); display link secrets kept out of logs; stored adapter recordings now really deleted; uploads always land on the staging key first; machine access grants scoped to one space; machine scope and PIN attempt budgets on adapter routes; usernames no longer revealing which accounts exist; and several smaller hardening changes. See the [security summary](security-summary-0.12.0.md).
- **Rate limits.** A generous deployment-wide ceiling now covers every route without its own limit (per account, per device or per client IP), and profile lookups, username checks, display claims, Anthias tests and adapter routes have their own. Every rate has an environment variable; see the [environment reference](environment-reference-delivery.md).
- **Redis.** Installs use Redis by default, bundled (pinned to a patch release, with a persistent append-only volume and a memory cap that never evicts the job queue) or external; a small install can still choose "no Redis" (scheduled jobs run from cron) as an explicit opt-in. If Redis goes down the API stays up: rate-limit counters fall back to per-process memory, and single-use security checks refuse with a retry instead of passing. TLS (`rediss://`) is verified. See [Redis](architecture/redis.md).
- **Sign-in methods.** One guide lists every method with its switch, throttle and lockout rules: [Sign-in methods](guide/sign-in-methods.md). Removing someone's last way to sign in (passkey, phone, social) is refused, linked identity providers are locked once linked, and claim codes sit behind the login IP guard.

## For operators


- Direct-room notification delivery fails closed when its lookup errors: nothing is sent and no quota is spent, while independent email delivery remains eligible.
- The web telemetry settings endpoint requires a signed-in active account with no pending password change. Revoking a person's authentication now also ends their personal access tokens and disconnects their OAuth app connections.
- Linked mutations (event/booking loan context, the loan repair handoff and the Shop pickup move) are session-only; their reads remain available to API bearer clients. The event booking link is session-only for reads and writes.
- New settings are listed in the [upgrade guide](upgrade-to-0.12.0.md#new-environment-variables). The Django settings that govern device adapters (offline-list key rotation, artifact retention, telemetry rollups, TURN) are listed in the [environment reference](environment-reference-delivery.md#device-adapters), next to `CERTIFICATE_SHARED_RENDERER`. None is required.
- The API schema advertises version 0.12.0 with 2,211 paths. See the [upgrade guide](upgrade-to-0.12.0.md) for the new migrations, including one non-atomic concurrent index build, and the [security verification summary](security-summary-0.12.0.md) for completed and pending checks.

## Verification status

This is release documentation for a build that has not finished its release gates. The complete backend regression, the browser/role/module/money matrix, PostgreSQL scenarios for the new connections, deployment and old-version upgrade rehearsals, a proven 0.9.2 rollback and exact final-image checks are still pending. Earlier passing results for the 0.11.0 candidate do not establish that this release is green. The sample limits and physical-printer limits recorded in the [0.11.0 candidate notes](release-0.11.0.md#verification-and-accepted-sample-limits) still apply.
