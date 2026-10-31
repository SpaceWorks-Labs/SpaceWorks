# Sign-in, identity and borrowing

How people sign in to Space Works, how a space runs without member accounts, who may ask to borrow
something, and how a superadmin chooses which ways in are offered. Staff roles and staff accounts are
covered in [Roles & access](README-HOSTING.md#roles--access).

## Sign-in methods

**Password sign-in works out of the box.** Google, Apple, GitHub and OIDC need credentials issued for
your domain; phone sign-in needs an SMS account. These provider/code methods are member-only.
Setup selects Google/Apple/GitHub options, and you enter provider keys later in the console. These keys
are separate from `GITHUB_API_TOKEN`, which enables the optional contribution count on maker profiles;
without that token the count stays hidden.

Sign-in providers resolve before a makerspace is chosen, so they are configured once for the whole
deployment (chat channels, by contrast, are configured per makerspace).

## Running without member accounts

Turning **Member accounts** off removes the member-account *ecosystem*: nobody signs themselves up, and
the member area, phone sign-in and the built-in Google/Apple/GitHub buttons all go with it. It does
**not** remove identity, and it never touches staff sign-in — a deployment that could switch off its own
staff logins could not be administered.

People still get named, two ways:

- **Your own identity provider.** A configured OIDC provider (Keycloak, Authentik, Azure AD, Okta,
  Google Workspace) keeps working, because it is your institution's directory rather than an account
  ecosystem this deployment runs.
- **Walk-ins.** Front-desk staff add someone at the counter from the handout screen. That creates a
  person record — a name, optionally an email and phone — with **no password and no way to sign in**.
  It is enough to issue them a tool, register them for an event or run a machine job for them, and it
  keeps every handover attributable to a real person, which the hardware rules require.

## Who may ask to borrow something

Borrow requests are a proposal: staff acceptance reserves stock. Who may ask follows from the modules;
there is no separate switch:

| Member accounts (`member_accounts`) | Membership (`membership`) | Who may submit |
| --- | --- | --- |
| on | on | **Members** — an active member of that makerspace |
| on | off | **Account holders** — anyone signed in |
| off | off (Membership needs Member accounts) | **Everyone, no account** — name, phone and email, the email confirmed with a one-time code |

Members must pass the applicable presence, waiver and current-term checks; account holders must be
active and unrestricted. Without member accounts the space's accounts are for staff only, so everyone —
even someone signed in — gives their name, phone and email (for self-checkout too) and types the 6-digit
code mailed to that address before the request is filed — nobody can file a request against someone
else's email. Phone and email are stored encrypted and shown to staff only; the name is the borrower's
public name. Every such request is recorded against the makerspace's single shared requester principal,
which every per-person ranking excludes. Borrower history and identity-based lookup use the
authenticated owner, never matching submitted email/phone. Existing request status links remain
bearer-token reads.

## Choosing which ways in you offer

**`/control/` → Platform login methods** switches the four member credential kinds independently:
password, identity provider, phone code, and self sign-up. All four are on by default and switching one
off never deletes anything, so turning it back on needs no re-entry.

Each switch covers **every member** way in of that kind, including delegated helper workspaces.
Staff and platform accounts always retain password sign-in (+ local MFA where required).
Turning member passwords off also refuses a mobile app's device login, which would otherwise mint a
long-lived session from the same password. Turning self sign-up off also stops an identity provider from
creating a brand-new account — signing in on an already-linked account, and linking a provider to an
account you already have, both keep working, because neither is a registration.

Existing sessions are deliberately **not** revoked: a login-method switch is a policy change, not a
revocation. Use the restrict/suspend flow to end someone's access.

Changes that would strand a member with only a disabled provider are refused. Staff/platform
accounts do not count social identities as alternative credentials and cannot use member recovery.
Staff passwords can be issued by an authorized administrator. Staff and platform sign-in also offer
**Forgot password?** using a six-digit email code through configured Platform Email. Staff recovery
stays within the selected makerspace; platform recovery uses the platform console. MFA remains
required after recovery. The host command remains available for platform break-glass recovery.
