---
title: How-to guides
group: How-to guides
order: 1
summary: Task-focused guides for operators: each one gets a specific job done from start to finish.
---

# How-to guides

Each guide solves one job for a space operator or self-hoster. Pick the task you need; every page lists what you need first and how to check it worked. If you are new, start with [Getting started](../guide/getting-started.md) or the [tutorials](../tutorials/overview.md).

| Page | What it covers |
| --- | --- |
| [Use your own domain with HTTPS](custom-domain.md) | Point a domain you own at your space, prove you control it and serve it over HTTPS. |
| [Send email through your own provider](email-sending.md) | Choose SMTP or an email API provider for a space, and understand what falls back to the platform sender. |
| [Send alerts to a Telegram group](telegram-alerts.md) | Connect a Telegram bot, add group rooms and choose which alerts each room hears. |
| [Set up SMS and WhatsApp](sms-whatsapp.md) | Add Twilio SMS or Twilio/Meta WhatsApp as a personal notification channel and understand consent. |
| [Choose and configure sign-in methods](sign-in-methods.md) | Turn on Google, GitHub, Apple, single sign-on (OIDC) and phone sign-in, and decide which ways in you offer. |
| [Two-step sign-in for staff and superadmins](staff-and-superadmin-mfa.md) | Enrol an authenticator or passkey, understand the staff grace period and recover a locked-out account. |
| [Turn an area or add-on on or off safely](turn-areas-on-off.md) | Switch Inventory, Machines, Events, Bookings, the Shop and add-ons for a space without losing data. |
| [Give someone a role](roles-and-handover.md) | Invite or grant the built-in staff roles, combine them, scope Machine Managers and Technicians, and set up a front-desk Handover role. |
| [Import members and inventory from a spreadsheet](import-members-and-inventory.md) | Bring members and inventory in from CSV, TSV or Excel, preview every change first and review the result. |
| [Export your data](export-your-data.md) | Request a readable copy of your space's records, and know how it differs from a backup. |
| [Set up offsite backups and restore](offsite-backups.md) | Add an S3-compatible offsite destination, check that copies are verified, and pick the right restore. |
| [Move a space to another server](move-a-space.md) | Export one space from the old server and import it on a new one, with identities, secrets and evidence intact. |
| [Add Apple Wallet and Google Wallet passes](wallet-passes.md) | Switch on wallet passes, add signing credentials for a space or the whole server, and test them. |
| [Remove card photo backgrounds](background-eraser.md) | Connect your own background-removal service, switch it on, and use it on card photos one by one or in a bulk upload. |
| [Design cards and certificates](design-cards-and-certificates.md) | Use the Card Studio for member cards, badges, tickets and event certificates, start from a template and save your own. |
| [Add web analytics, replay and error tracking per space](web-telemetry.md) | Configure Plausible, Umami, GA4, PostHog, Clarity or Sentry for one space, with visitor consent. |
| [Set prices, rate cards and fees](rate-cards-and-fees.md) | Decide per area whether the space charges nothing, records debts to settle offline, or takes online payment, then set rates. |
| [Privacy and terms pages](privacy-and-terms.md) | Edit the platform text, let a space write its own and see where visitors read them. |
| [Set up guest passes and waivers](guest-passes-and-waivers.md) | Let non-members visit on a dated pass, choose what a pass unlocks, require a waiver and sell day passes. |
| [Admit minors with guardian consent](minors-and-guardian-consent.md) | Turn on minors, set ages and what they may do, and understand how consent is recorded and expires. |
| [Let people check in by location](presence-check-in.md) | Configure a geofence for self check-in, choose privacy for the who's-in display, and fall back to staff check-in. |
| [Rotate encryption and secret keys](rotate-keys.md) | Which keys can be rotated, how, and which ones you must never change casually. |
| [Run behind a reverse proxy and reach the control plane](reverse-proxy-and-control-plane.md) | Put nginx or another proxy in front of SpaceWorks, and open /control/ safely over an SSH tunnel. |
| [The SpaceWorks front page and the Features page](front-page-and-features.md) | See what the product page and the Features page show and switch the front page on or off. |
| [The global member profile](member-profile.md) | One profile per account, what goes on it, who sees it and what is never shown. |
| [Usernames](usernames.md) | How every account gets a username, the sign-up field, the choose-your-username step and reserved names. |
| [Use a shelf pointer](shelf-pointer.md) | Calibrate a laser or LED pointer, show items on the shelf, guide a stocktake with it and save shelf checks. |
| [Public space page and display screens](display-screens.md) | Show who is here now, machines and the events calendar publicly, and pair a TV display. |
| [Log machine use for an event](machine-use-for-events.md) | Tag a session or job as done for an event, let the area manager set it, see it on the event page, and what "charge the event" does. |
| [Machine printing and connecting machines](machine-printing.md) | What printing support ships now, and how vendor adapters plug in later. |
| [Set up machine types and their consumables](machine-consumables.md) | Add any machine type from a template, choose what it uses up and in which units, price it, link stock, and record use on jobs. |
| [Give members machine access](machine-access.md) | Grant machine access to chosen members, with an optional end date; what replaced certifications. |
| [Manage device adapters](adapter-console.md) | Enrol a bridge, bind it to machines, shelves and doors, and use the staff console for camera, audio, timelapses, offline access and kiosk checkout. |
| [Upgrade SpaceWorks safely](upgrade-safely.md) | Prepare, update with the installer or runner, verify readiness and know what a rollback really means. |
