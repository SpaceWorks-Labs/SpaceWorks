---
title: In-app configuration map
group: Reference
order: 20
summary: Every settings group and page in the staff console and the platform console, with one line each.
---

# In-app configuration map

Most configuration lives in the app, not in files. **Settings** in the staff console belongs to one space; **Platform settings** belongs to the whole server and is for the superadmin. Server environment variables are separate: see the [environment reference](../environment-reference.md).

> **Note** A page for an area that is switched off is absent, not empty. If you cannot find a page, check **Areas & add-ons** and the capability switches under **Settings > Areas > Features** first.

Settings are grouped the same way in both consoles: Space, People, Areas, Money, Communication, Integrations, Administration. Some entries open a console page of their own (marked "opens page").

## Space settings

### Space

| Page | What you set |
| --- | --- |
| Overview | A hub of shortcuts and what still needs setting up |
| Profile & location | Name, description, contact details and location |
| Branding & public site | Logo, banner, colours, print status recovery policy, subdomain (hosted platforms), your own domain or frontend, and **Hide this space from the platform** |
| Public page | The page builder for the space's public home |
| Public stats | Which figures and lists appear on the public stats page and TV view |

### People

| Page | What you set |
| --- | --- |
| Staff & roles (opens page) | Grant, invite and revoke staff roles, per-person machine types, staff MFA reset |
| Membership | How people join (instantly, by approval, invite-only), referrals, lapsed-member borrowing, dues, the presence geofence and wallet passes |
| Guest passes | Guest borrowing and machine rules, sponsor liability, waiver requirement, visit limits, day passes |
| Community | Minors and guardian consent, volunteer credit, the join follow-up |
| Presence privacy | The public who's-in display: names and opt-out |

### Areas

| Page | What you set |
| --- | --- |
| Areas & add-ons (opens page) | Turn areas and add-ons on or off |
| Features | Capability switches inside each area, and space packs where enabled |
| Inventory | Borrow request access, loan policy, pickup windows, reservations and waitlist, reminders, kiosk stations |
| Machines & materials | Filament and material settings |
| Events | Event defaults |
| Bookings | Booking settings and rules |
| Shop settings (opens page) | The shop's own settings |

### Money

| Page | What you set |
| --- | --- |
| Payments & billing | Payment provider and money mode, billing documents, tax, event money |
| Pricing | Rate cards, per-item prices, discounts |
| Donations profile (opens page) | The non-profit profile for donations and sponsors |

### Communication

| Page | What you set |
| --- | --- |
| Notifications | Staff email on or off, timing, the mute matrix, who is notified, rooms and chat templates |
| Communication channels | Credentials and senders for Email, Telegram, Slack, Mattermost, Discord, SMS, WhatsApp and app push, plus the delivery log |
| Email sending | The space's email provider and sender |
| Email templates, Email logs (open pages) | Wording of emails, and a log of what was sent |

### Integrations

| Page | What you set |
| --- | --- |
| Webhooks | Chat webhooks for Slack, Mattermost and Discord, and Telegram for superadmins |
| Integration health | Status of each configured integration |
| API access (opens page) | API clients, app connections and their scopes |

### Administration

| Page | What you set |
| --- | --- |
| Privacy & evidence | Evidence photo retention window |
| Invite a makerspace | Hosting invitations, when hosting other spaces is on |
| Security (opens page) | Staff sign-in requirements, platform access to personal data, encryption key history |
| Audit, Data export, Backup & restore, Usage (open pages) | The audit log, readable exports, backups and restore points, usage and limits |
| Tenant migration (superadmin) | Moving a space between servers |

## Platform settings (superadmin)

| Group | Page | What you set |
| --- | --- | --- |
| People | Sign-in providers | Google, Apple and GitHub credentials, and which sign-in methods are offered |
| People | Single sign-on | Your own OIDC identity providers |
| People | People & access (opens page) | Accounts, staff and Space Managers across every space |
| Areas | Feature defaults | What a new space starts with and how many spaces use each feature |
| Money | Stripe Connect | Hosted spaces' card payments (only when hosting other makerspaces is on) |
| Money | Plans & limits (opens page) | Each space's plan, fair-use limits and billing |
| Communication | Email | The platform sending server and address |
| Communication | Messaging providers | Shared SMS, WhatsApp and push accounts |
| Communication | Chat templates | Default wording of chat and SMS messages |
| Integrations | Mobile apps | Phone apps allowed to sign in and their links |
| Integrations | Wallet passes | Platform wallet-pass credentials |
| Administration | Version & deployment | Which version runs and how the server is set up |
| Administration | Platform security (opens page) | IP rules, sign-in blocks, security locks, audit log |
| Administration | Data & recovery (opens page) | Backups, offsite copies, restore drills, space moves and imports |

## Related guides

- [Turn an area on or off safely](../how-to/turn-areas-on-off.md)
- [Send email through your own provider](../how-to/email-sending.md)
- [Set prices, rate cards and fees](../how-to/rate-cards-and-fees.md)
- [Choose and configure sign-in methods](../how-to/sign-in-methods.md)
