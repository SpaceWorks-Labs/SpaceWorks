---
title: FAQ and troubleshooting
group: Getting started
order: 40
summary: Short answers to common questions and first checks when something does not work.
---
# FAQ and troubleshooting

## General

**Is it free?** Yes. Space Works is open source under AGPL-3.0-or-later. Hosting costs are yours.

**Do I need to be a developer to run it?** No. The installer asks plain questions. See [setup for makerspaces](../setup-for-makerspaces.md).

**Can one install run several makerspaces?** Yes. Each space is isolated. Hosting other makerspaces is an optional switch for the platform owner. See [choose your hosting](../choose-your-hosting.md).

**Do members need accounts?** Not necessarily. You can turn Member accounts off; staff still sign in, and front-desk staff add walk-ins at the counter. Without accounts, requests need a name, phone and email, with the email confirmed by a one-time code. See [sign-in and borrowing](../sign-in-and-borrowing.md).

**Why can't I issue without a photo?** It is a deliberate rule. Issuing needs a box scan and an issue photo; returning needs a return photo and a remark. Traceability is the product.

**Can I switch features off?** Yes. Modules and features are opt-in; a feature that is off disappears from the interface. See [choosing modules](../choosing-modules.md).

## Sign-in

**I forgot my password.** Use the reset page at `/reset-password`: a six-digit code is emailed, then you set a new password. Staff must still pass their second factor afterwards.

**A staff member lost their authenticator.** MFA resets follow a controlled reset rule, and a Space Manager cannot reset another person's factors. Ask a platform administrator. A person who gains a role without two-step sign-in gets a single 3-day grace.

**Google, Apple or GitHub sign-in is missing.** Those methods need provider credentials entered once for the whole deployment, and the login method must be enabled by the platform. Password sign-in works without any setup.

## Install and updates

**The installer stops on a dependency.** It prints a dependency plan first. On Linux it can install Docker Engine and Compose V2 after confirmation. On Windows use Docker Desktop with Linux containers and run from Git Bash. See [install and update](../install-and-update.md).

**The site does not load after install.** Check that Docker is running and that all containers are healthy. The stack includes the database, Redis, object storage, the backend, workers, the scheduler and the frontend. Then read [self-hosting](../self-hosting.md).

**An update went wrong.** Updates take a pre-update database dump into the `backups` folder. See [database recovery after an update](../update-recovery.md) and [backup and restore](../backup-and-restore.md).

**Where is the admin interface?** Staff work in the React console at `/admin`. The Django control plane for platform operators lives at `/control/` and is not reachable on the public port unless an operator enables it.

## Notifications

**Messages are not arriving.** Turning a channel's module on does not start sending by itself. Add the credential, then enable the events you want in the per-feature by per-channel matrix. SMS and WhatsApp also need member consent and sender configuration. See [notification channels](../notification-routing.md) and [SMS and WhatsApp](../messaging-channels.md).

**Chat messages never show amounts.** Financial amounts are deliberately kept out of staff chat.

## Photos and data

**An old photo no longer opens.** Photo bytes expire after the retention window (365 days by default). The record, remarks, scans and audit trail remain. See [data and privacy](../architecture/data-and-privacy.md).

**Can a member delete their account?** Yes, once outstanding obligations are settled. Identity copies are archived for 90 days by default, then purged. See [account deletion](../privacy-account-deletion.md).

## Money

**Do I need Stripe or Razorpay?** No. Debts are recorded without any online rail, and staff can mark a charge paid offline with a receipt. The online rail is optional. See [payments and billing](../payment-billing.md).

## Developers

**Where is the API reference?** Every deployment serves Swagger UI at `/docs/`, ReDoc at `/redoc/` and the schema at `/schema/`. See [the API guide](../api-guide.md).

**Where do I report a bug or contribute?** Use the GitHub repository at https://github.com/SpaceWorks-Labs/SpaceWorks.
