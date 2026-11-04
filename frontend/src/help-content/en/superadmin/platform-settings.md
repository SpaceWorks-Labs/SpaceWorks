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

Saved secrets stay hidden; leave a field blank to keep it. Clearing a payment credential can stop connected payments.

![Screenshot: Platform settings with the Email section](screenshot:sa-platform-settings)

Which sign-in methods exist at all (password, providers, phone codes, self sign-up) is chosen at install time and changed from the server.

## Hosting requests

On a hosted platform, spaces ask to be hosted:

1. In `/control/`, open **Hosting requests**.
2. Accept, reject (the reason is emailed) or ask for changes.
3. On an accepted request, press **Create makerspace**, confirm your identity and complete the pre-filled form.

Nothing is created automatically.

> **Who can do this:** the platform superadmin.
