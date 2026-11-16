# Notification channels, rooms and recipients

How a space decides where its alerts go: which channels it runs, which room hears about which machine
or category, who is notified about what, and the wording they receive. Channel credentials and the
personal delivery contract are covered in [Notifications v2](notification-contract.md),
[SMS and WhatsApp](messaging-channels.md) and [Personal notifications](notification-inbox.md).

## Notification channels are modules

`email`, `telegram`, `slack`, `mattermost`, `discord` and `webhook` are each a module, so a space that
lives in Discord ships no Slack surface at all. Turning a channel's module on never makes it start
sending on its own — you still add the webhook or token, and you still enable the events you want in
the per-feature × per-channel matrix. Turning it off stops delivery but **keeps the stored credential**,
so re-enabling needs no re-entry.

Chat channels are configured **per makerspace** (the space owns the channel and pays for it). Sign-in
providers are the opposite — they resolve before a makerspace is chosen, so they are configured once
for the whole deployment.

## Rooms: sending different alerts to different places

A chat channel can have more than one **room** — a Slack channel, a Discord channel, a Telegram group.
Add them under **Settings → Notification channels → Rooms**. A room with nothing selected receives
everything; narrow one to a machine, a machine type or an inventory category and it receives only
those alerts. "All the 3D printers, plus the laser" needs no extra concept — the selections are a
union.

Two things worth knowing before you set this up:

- **Webhook URLs are write-only.** They are stored encrypted and never shown again, so an edit that
  only renames a room can leave the field blank.
- **Signed webhooks get a generated secret, shown once.** Create a `webhook` room without a secret and the server makes one and returns it in that response only; it can never be read again. 
  **Rotate** it with `POST .../notification-destinations/{id}/rotate-secret` (optional `grace_hours`, default 24, 0 to retire the old one at once). During the grace window each delivery carries one `v1=` signature per live secret, newest first, so the receiver can switch over without dropping events.
- **Telegram rooms share the makerspace's bot** — add the same bot to each group and paste each
  group's chat ID. Rooms use the Communication channels bot token when configured, then the legacy
  tenant/platform fallback. Decisions remain in the staff console or `/control/`; every decision
  callback is ignored and no alert carries a keyboard. The webhook accepts verified private `/start`
  account-link proofs only; setWebhook must include `message` in allowed_updates.

A makerspace that has added no rooms keeps using the single webhook under **Chat webhooks**, exactly
as before. Nothing changes until you add your first room.

## Choosing who hears about what

By default every alert goes to everyone whose role covers it — a booking alert reaches whoever can
manage bookings. Under **Settings → Notification channels → Who gets notified** you can override that
per event, for events, bookings, maintenance and members. A recipient can be:

| Recipient | Means |
|---|---|
| A role | Everyone currently holding that role |
| A named member | One person, who must be a member of this makerspace |
| All members | The whole membership |
| The person it is about | The requester, booker or registrant |

**Leaving an event empty is the default, not silence** — remove every recipient and it goes back to
notifying by role. A member who has switched their own notifications off is never mailed, even when
somebody selects them.

Recipients can be narrowed by machine or category the same way rooms are, and the narrowing can only
ever *reduce* who is notified: a person is never alerted about a machine their role cannot see.

## Editing the wording

**Settings → Email templates** covers hardware, printing, events, bookings, maintenance and
membership, for both the member-facing and staff-facing message. Each template lists the variables it
can use and previews against sample data, and a saved template can be reset to the built-in wording at
any time. Chat messages have one editable body per event, shared by all four chat channels — so you
edit the wording once rather than four times.

Chat rooms only ever receive the **staff** wording. Member-facing text ("your booking is confirmed")
goes to email and to the member's phone, never into a shared room where everyone with channel access
would see that member's name.
