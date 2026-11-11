---
title: Choose and configure sign-in methods
group: How-to guides
order: 50
summary: Turn on Google, GitHub, Apple, single sign-on (OIDC) and phone sign-in, and decide which ways in you offer.
---

# Choose and configure sign-in methods

Password sign-in works out of the box. Everything else needs credentials issued for your domain. Sign-in providers are configured **once for the whole server** by the platform superadmin, because people sign in before a space is chosen. (Chat channels, by contrast, are per space.)

## Before you start

- You are the platform superadmin.
- Your site is served over HTTPS on its final domain; providers register that domain.

## Google, Apple and GitHub

1. Open **Platform settings > People > Sign-in providers**.
2. Fill in the provider you want:

| Provider | You enter |
| --- | --- |
| GitHub | OAuth App **client ID** and **client secret** |
| Google | **Web client ID**, plus iOS and Android client IDs if you ship mobile apps |
| Apple | **Web Service ID**, native app audiences, Team ID, Key ID and the `.p8` private key |

3. Save. Secrets are write-only: a saved secret shows as "set", and you leave the box blank to keep it.

> **Note** These keys are separate from `GITHUB_API_TOKEN`, which only powers the optional contribution count on maker profiles.

Setup can pre-select providers (`python manage.py set_login_methods --providers google,github` changes the install-time choice, and `configure_social_auth` sets Google client IDs from the host), but the console is the normal place.

## Your own identity provider (OIDC)

Use this for a university, company or Keycloak/Authentik/Azure AD/Okta directory.

1. Open **Platform settings > People > Single sign-on** and expand **New provider**.
2. Enter the **Name on the sign-in button**, a **Short name** (letters, digits, `-`, `_`; linked sign-ins are stored under it), the **Issuer** exactly as the provider publishes it, the **Key set address (JWKS)** and your **Client ID**.
3. Decide whether to **Link a first sign-in to an existing account when both emails are verified**. Leave it off if you do not fully trust the provider's email verification.
4. Tick **Turn it on now** or turn it on later.

Providers cannot be deleted, because people's linked sign-ins depend on them; turn one off instead.

## Phone sign-in

Phone codes need a platform SMS account. Add it under **Platform settings > Communication > Messaging providers**, then switch **Phone sign-in** on below.

## Choose which methods you offer

On the same page, **Sign-in methods** has independent switches: **Password sign-in**, **Google, Apple and GitHub sign-in**, **Phone sign-in**, **People may create their own account** and **Passkeys**. Turning one off never deletes anything, so turning it back on needs no re-entry.

- A switch that would strand someone with no way in is refused.
- Staff and platform accounts always keep password sign-in (plus two-step sign-in where required).
- Turning self sign-up off also stops an identity provider from creating brand-new accounts. Signing in to an already linked account, and linking a provider, keep working.
- Existing sessions are not ended. Use restrict or suspend to end a person's access.

If you switch **Member accounts** off for the space entirely, built-in Google/Apple/GitHub and phone sign-in go with it, but a configured OIDC provider and staff sign-in keep working. See [Sign-in, identity and borrowing](../sign-in-and-borrowing.md).

## Verify

Sign out and open the sign-in screen: each enabled method shows a button or field. Sign in once with a test account for each method before announcing it.

## See also

- [Two-step sign-in for staff and superadmins](staff-and-superadmin-mfa.md)
- [Sign-in, identity and borrowing](../sign-in-and-borrowing.md)
