---
title: Platform settings, sign-in providers and hosting requests
summary: Set up platform email, social sign-in and Stripe Connect, and handle requests from spaces wanting hosting.
order: 100
keywords: platform settings, email, smtp, google, apple, github, sign-in providers, stripe connect, hosting requests, login methods
---
## Platform settings

Open **Platform settings**:

- **Email**: the instance-wide mail used for sign-in, password resets and spaces that don't set their own.
- **Sign-in providers**: Google, Apple and GitHub sign-in for members.
- **Stripe Connect** (hosted platforms): your platform keys and fee.
- **Deployment**: read-only facts about this installation.
- **Messaging & apps**: deployment-wide messaging providers and app configuration.
- **Mobile apps**: registered app identities and readiness checks. Read each failed check's hint before changing its provider or app identity.
- **Audit log**: actions across spaces. Search by action or actor, filter by makerspace ID, or select **Platform-level rows only**.
- **Restore drills**: recovery test history and results.
- **Accounts**, **IP access** and **Single sign-on**: platform security controls.

Saved secrets stay hidden; leave a field blank to keep it. Clearing a payment credential can stop connected payments.

![Screenshot: Platform settings with the Email section](screenshot:sa-platform-settings)

Under **Sign-in providers**, **Sign-in methods** controls the available login methods. Deployment settings and configured providers still determine whether each method can be used.

## Hosting requests

On a hosted platform, spaces ask to be hosted:

1. Open **Spaces → Onboarding** in the platform console, or use **Hosting requests** in the server control plane.
2. Accept, reject (the reason is emailed) or ask for changes.
3. On an accepted request, press **Create makerspace**, confirm your identity and complete the pre-filled form.

Nothing is created automatically.

> **Who can do this:** the platform superadmin.
