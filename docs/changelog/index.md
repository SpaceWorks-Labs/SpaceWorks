---
title: Changelog
group: Changelog
order: 10
summary: What changed in each SpaceWorks release, newest first, with links to the full release notes.
---

# Changelog

Releases are published from `main` and titled **SpaceWorks `<version>`**. A deployment pins to a build tag such as `v0.12.0-main.<run>.<sha>`. Upgrades only move forward: see [Upgrade safely](../how-to/upgrade-safely.md). The full, file-level changelog is [CHANGELOG.md](https://github.com/SpaceWorks-Labs/SpaceWorks/blob/dev/CHANGELOG.md).

## 0.12.0

The first published release after 0.9.3. It also carries everything prepared for the unpublished 0.11.0 candidate. Full notes: [release notes](../release-0.12.0.md), [upgrade guide](../upgrade-to-0.12.0.md) and [security verification](../security-summary-0.12.0.md).

**Highlights**

- **Inventory, not Lending.** One Inventory area, with its own page and a separate makerspace overview, switchable per space like any other area.
- **Contextual lending and kits.** A loan can be tied to an event registration, an exact booking or both, and requesters can pick a published equipment **kit** ([contexts](../equipment-contexts.md), [kits](../equipment-kits.md)).
- **Guest passes and day passes.** A dated permit for non-members, sponsored, issued by staff, linked to an event or bought. See [Set up guest passes](../how-to/guest-passes-and-waivers.md).
- **Fixed staff roles.** Built-in roles that combine (Technician, Shop Manager, Fundraising and Handover included) replace editable roles; Machine Manager reach is per person by machine type. See [Roles and permissions](../reference/permissions.md).
- **Events, hackathons and the Shop.** Configurable submission stages, judging, ticketing and applications; member cards and certificates; front-desk shop sales, pickup and cash-up.
- **Money you can run free, offline or online.** Record what is owed without a payment provider; online checkout is an optional rail. Full precision for three-decimal currencies. See [Rates and fees](../how-to/rate-cards-and-fees.md).
- **A scrolling front page and a Features page.** Every site opens on a product page that a space can switch off at install or later. See [The front page](../how-to/front-page-and-features.md).
- **One global profile and a username for everyone.** Visible to signed-in members by default, with a separate open-web switch, achievements, projects and status. See [The global member profile](../how-to/member-profile.md) and [Usernames](../how-to/usernames.md).
- **Here now, Machines now, a calendar and TV display screens** on the public space page. See [Display screens](../how-to/display-screens.md).
- **Machine printing foundation.** Print requests, label printers and enrolled printers, with vendor adapters to come. See [Machine printing](../how-to/machine-printing.md).
- **Donations and sponsors** for non-profits.
- **Each role sees what it manages.** Area managers get their own finance, To-Buy, repairs and warranty views.
- **One self-hosted mode, a standard installer and hybrid setup.** A signed, checksummed one-line installer, standard backend and frontend images, and the option to keep the database, Redis, storage or email outside the server.
- **API access.** Personal access tokens and OAuth app connections, API client scopes by area, peer clients between spaces, signed webhook payload v2. See the [API section](../api/overview.md).
- **Analytics.** Grafana beside Metabase, each reading only curated, read-only per-space data.
- **Backups and recovery.** Verified offsite copies, restore drills and one-space restore points. See [Offsite backups](../how-to/offsite-backups.md).
- **Platform administration.** Reversible space controls, a platform overview and audit views, an optional control-plane route and SSH-tunnel listener.
- **Machines.** Machine service covers every machine type (the Printing module is folded into it), with per-type consumable profiles, an "Add a machine type" setup, machine use logged with an event and a shelf pointer for staff. See [Machine consumables](../how-to/machine-consumables.md) and [Use a shelf pointer](../how-to/shelf-pointer.md).
- **Display screens and Anthias.** Choose the panels each screen shows and run them on an Anthias player. See [Anthias](../how-to/anthias.md).
- **Card Studio.** Rulers, print-ready PDF, more barcodes, version compare and a background-eraser opt-out. See [Design cards and certificates](../how-to/design-cards-and-certificates.md).
- **Security and resilience.** Every finding of the 0.12.0 security reviews is fixed, rate limits cover every route, and Redis is pinned and survives an outage. See [Redis](../architecture/redis.md) and [Sign-in methods](../guide/sign-in-methods.md).
- **Language and help.** A language switcher and role-specific help.

**Upgrading notes**

- From 0.9.x, preview and run the irreversible fixed-role conversion before updating ([steps](../update-recovery.md#fixed-role-upgrade-2026-10-16)).
- The all-in-one image is gone; installs must use the standard containers.
- One migration builds an index concurrently on the audit log; allow time on large logs.

## 0.11.0 (candidate, never published)

Folded into 0.12.0. Its [notes](../release-0.11.0.md) remain as history. It introduced the separate Inventory page and overview, public-stats controls, account-owned history, Technician and Shop Manager roles, the Shop, member cards and certificates, personal API access and OAuth app connections, one account per person, and the Space Works design system.

## 0.9.3 (2026-11-08)

- Fresh Docker installs complete backup-capability initialisation.
- Installer and deployment defaults follow the SpaceWorks-Labs repository and image names.
- Published backend images get an installer smoke check.

## 0.9.2 (2026-10-14)

- Deploys run on a **self-hosted GitHub Actions runner** after each release, gated by the `SPACEWORKS_DEPLOY` repository variable. `update.sh --version` deploys an exact published release.
- The 0.9.1 deploy webhook is removed.

## 0.9.1 (2026-10-14)

- Updates run from the host, with locking, pre-update dumps, migration and readiness gates and image rollback; in-app update control is removed.
- The installer asks every decision first and shows a summary before changing anything.
- Object storage runs on Silo, the maintained MinIO fork, reading existing volumes unchanged.
- The demo seeder refuses production databases.

## 0.9.0 (2026-10-12)

The feature-research programme:

- **Module-family independence.** A space can run events-only, bookings-only, machines-only, membership-only or inventory-only.
- **Events.** Registration audiences, ticket types, promo codes and public event pages.
- **Membership.** Admission, vouching, renewal automation and member self-service.
- **Payments and reports.** Reminders, numbered receipts and credit notes, finance and membership analytics, scheduled reports.
- **Notifications.** Personal inbox, quiet hours and digests, bounce handling and broadcasts.
- **Platform.** Staff MFA and invitations, space packs, a creation wizard and organization linking.

## 0.7.5 and earlier

Versions 0.3.0 to 0.5.1 were never recorded in the changelog file; the condensed [project history](../PROJECT-HISTORY.md) lists what shipped and when, newest first, back to the first production deployment on 2026-06-19.

## See also

- [Project history](../PROJECT-HISTORY.md) for the condensed per-batch log.
- [Upgrade to 0.12.0](../upgrade-to-0.12.0.md)
