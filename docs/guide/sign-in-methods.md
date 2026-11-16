---
title: Sign-in methods
group: Getting started
order: 35
summary: Every way people can sign in, who can use each one, how to switch it on and what it needs.
---
# Sign-in methods

Space Works has one account per person. Whichever way someone signs in, they land in the same
account, and what they can do there depends on their roles in each space, never on how they signed in.

The platform owner (the superadmin) decides which methods the whole deployment offers. These switches
are under **Platform console → Login methods** (or `/control/` → *Platform login methods*). They apply
to every space on the server, because sign-in happens before anyone has picked a space.

## At a glance

| Method | Who can use it | Switched on by default | What it needs |
|---|---|---|---|
| [Password](#password) | Everyone | Yes | Nothing |
| [Email codes](#email-codes) | Everyone with an email address | Always on | Working email |
| [Two-step sign-in (authenticator app)](#two-step-sign-in) | Everyone; **required for staff** | Chosen at install | Nothing |
| [Recovery codes](#recovery-codes) | Anyone with two-step sign-in | Comes with two-step sign-in | Nothing |
| [Passkeys](#passkeys) | Everyone, on the website | Yes | The website on its own domain |
| [Google](#google-apple-and-github) | Members | Chosen at install | Google client IDs |
| [Apple](#google-apple-and-github) | Members | Chosen at install | Apple service ID and app IDs |
| [GitHub](#google-apple-and-github) | Members, on the website | Chosen at install | A GitHub OAuth app |
| [Your own identity server (OIDC)](#your-own-identity-server-oidc) | Members | When you add one | Issuer, key address, client ID |
| [Phone code (SMS)](#phone-code-sms) | Members with a verified number | Yes | An SMS provider |
| [Mobile app sign-in](#mobile-apps) | Everyone, in the official apps | When the app is registered | App registration |
| [Claim codes](#claim-codes) | Walk-in members staff added at the desk | Always on | Staff hand out the code |
| [Machine and kiosk PINs](#machine-and-kiosk-pins) | Members at a machine or kiosk | Per space | A connected device |
| [Event check-in station PIN](#event-check-in-station-pin) | Staff running an event desk | Per event | Offline check-in feature |
| [Self sign-up](#self-sign-up) | Anyone new | Yes | The member accounts area |

## Password

A username or email address plus a password. Staff always keep password sign-in, even if you switch it
off for members, so you can never lock the team out of the console. New passwords are checked against
a list of passwords known from data breaches (when `PASSWORD_BREACH_CHECK_ENABLED` is on); if that
service cannot be reached the password is still accepted.

**Forgot password:** people ask for a 6-digit code by email and choose a new password.

## Email codes

Space Works sends a 6-digit code by email in three situations:

- to confirm a new member's email address after self sign-up;
- when a sign-in looks unusual (new device and new network) for someone without two-step sign-in;
- to reset a password.

Codes last ten minutes, allow five tries, and can be re-sent twice. You cannot switch email codes off,
because they are how people prove they own their address.

## Two-step sign-in

An authenticator app (Google Authenticator, 1Password, Authy and so on) adds a 6-digit code after the
password. Every staff role always needs a second step: an authenticator app or a passkey. New staff get
three days to set one up. Members can turn it on for themselves.

Whether members are offered it is chosen when the server is installed. Change it later on the server with
`manage.py set_login_methods --mfa on` (or `off`). Turning it off never deletes anyone's authenticator.

## Recovery codes

When someone sets up two-step sign-in they get ten one-time recovery codes. Each works once instead of the
authenticator code. If a person loses both, the superadmin can reset their two-step sign-in from the
console (or `manage.py reset_mfa` on the server). A space manager can reset someone whose staff roles are
all in that one space, but not another space manager. A reset is recorded and signs the person out
everywhere.

## Passkeys

A passkey uses the phone's or computer's own lock (fingerprint, face or PIN) instead of a password. People
add them under **Account → Security**. A passkey also counts as the second step for staff.

- Passkeys work on the website only, not inside the mobile apps yet.
- The website must be served from its own domain (the address people see in the browser). The name the
  browser shows is `WEBAUTHN_RP_NAME`.
- Switching passkeys off stops their use but keeps every passkey, so switching back on needs no re-setup.

## Google, Apple and GitHub

People sign in with an account they already have. These are for **members**: staff still sign in to the
console with their password and second step. If the provider confirms the same email address as an
existing, verified account here, the two are joined automatically; otherwise the person is asked to sign
in first and link it under **Account → Security**. An unverified email address never takes over an
existing account.

Which of the three your server offers is chosen at install (Google is the default). Change it later with
`manage.py set_login_methods --providers google,apple,github` (or `none`). Then enter the keys under
**Platform console → Social sign-in**:

- **Google:** a web client ID for the website, and iOS and Android client IDs for the apps.
- **Apple:** a Services ID for the website, the app IDs of the iOS app, and the private key (used to cancel
  Apple's access when an account is deleted).
- **GitHub:** create an OAuth app in GitHub (*Settings → Developer settings → OAuth Apps*). Set its
  *Authorization callback URL* to your website's address, for example `https://members.example.org/`, and
  enter the client ID and client secret. GitHub sign-in works on the website only.

The secrets are stored encrypted and are never shown again after saving.

## Your own identity server (OIDC)

If your organisation already has a sign-in server (Keycloak, Authentik, Microsoft Entra ID, Okta, Google
Workspace), add it under **Platform console → Single sign-on providers** with:

- a short name (the *slug*) and a display name for the button;
- the *issuer* exactly as the server writes it;
- the address of its public keys (*JWKS URL*);
- the *client ID* you registered there. No client secret is needed: sign-in uses PKCE.

Register your website's address as the redirect address at the identity server. Leave **Allow automatic
linking** on only if that server really verifies people's email addresses.

Once anyone has signed in through a provider, its short name and issuer cannot be changed: changing them
would point existing sign-ins at a different server. To move to another server, add it as a new provider.
To stop using one, switch it off; it cannot be deleted.

## Phone code (SMS)

Members who have added and verified a mobile number can sign in with a 6-digit code sent by text. It
needs an SMS provider (see [SMS and WhatsApp](../how-to/sms-whatsapp.md)). The answer is the same
whether or not a number is known, so the form cannot be used to find out who is a member. Phone sign-in
only ever gives a member session.

## Mobile apps

The official Android and iOS apps sign in with a password, a phone code, Google, Apple or your own
identity server, and each sign-in is tied to that installed app. GitHub and passkeys are website-only for
now. Staff in the app take an extra step (a second factor) before they can act for a space.

## Claim codes

When staff add someone at the desk who has no account (a walk-in), they can print a one-time claim code.
The person redeems it to reach their own loans and details, and can then add a password or another sign-in
method. A code expires, works once, and locks after five wrong tries.

## Machine and kiosk PINs

At a connected machine or self-checkout kiosk, members identify themselves with an NFC tag, their member
number and PIN, or the QR code on their member card plus PIN. A card QR code alone never opens anything.
Five wrong PINs lock that member's PIN for 15 minutes, and each device and each space also has a limit on
wrong guesses that pauses PIN entry for a while when reached. These PINs only work at the device; they never
sign anyone in to the website.

## Event check-in station PIN

A check-in desk at an event unlocks with a PIN that staff set for that event. It only works during the
event's check-in window and only for that event's desk.

## Self sign-up

Lets anyone create their own member account (needs the member accounts area switched on). With it off,
staff add people from the console, and people can still sign in with an identity provider only if they
already have an account here.

## Switching methods off safely

Space Works refuses a change that would leave someone with no way to sign in. A way in counts if it is
switched on and the person has it: a password, a linked provider that is still on, a verified phone with
phone sign-in on and SMS set up, or a passkey with passkeys on. The same rule stops a person from removing
their own last sign-in method (unlinking a provider or phone, or removing their last passkey). Members who
only ever used a password are the one exception: switching member password sign-in off is your decision,
and staff keep their passwords either way.

## Protection on every sign-in

- **Limits:** every sign-in, code and PIN form has its own limit per address and, where it makes sense,
  per account or number.
- **Blocking:** the superadmin can allow or deny address ranges, and an address that fails many different
  accounts is blocked for an hour automatically. A CAPTCHA (Cloudflare Turnstile) can be required instead,
  if configured.
- **Records:** successful and failed sign-ins, links, unlinks and resets are recorded in the audit log,
  without passwords or codes.
- **"This wasn't me":** security emails carry a link that signs the account out everywhere.
- **If the cache is unavailable**, sign-in keeps working. Limits are then counted by each server process on
  its own until the cache is back, so they are looser for a while but never switched off.
