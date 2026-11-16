---
title: Public space page and display screens
group: How-to guides
order: 250
summary: Choose what the public page and your TV screens show (here now, machines, events, public stats, opening hours, inventory highlights, sponsors), in what order and layout, how private names are, and preview it before you save.
---

# Public space page and display screens

A space's public page (`/m/<slug>`, or `/` on a space's own domain) can show three live sections, and the same information can run full-screen on a TV in the workshop. Each section appears only when the area behind it is switched on, and each one follows strict privacy rules.

## The three live sections

| Section | Shown when | What it shows |
| --- | --- | --- |
| **Here now** | The `presence` module is on | People checked in at the space, as cards (name, picture, headline, status, a few skills), plus a count of everyone else |
| **Machines now** | The `machines` module is on | Each public machine as **In use**, **Free** or **Out of service**, with counts such as "3 free, 2 in use, 1 out of service" |
| **Events calendar** | The `events` module is on | A month grid, a "Live now" card for events happening right now and a "Coming up" list. Only public, listed events appear |

**Machines now never shows who is using a machine**, and machines that are not public are left out.

### Who is named in "Here now"

| Viewer | Who gets a name and picture |
| --- | --- |
| Not signed in | Only people whose profile is open to the web **and** who did not hide their presence |
| Signed in | People whose profile is visible on the platform and who did not hide their presence |

Everyone else is counted, never named ("+ 7 makers in"). A person appears as a card only when all of these are true:

- The space has **Show names** switched on (otherwise everyone shows as "A member" or "A guest").
- The person did not choose **Hide me on the display** when they checked in. They then appear as "A member" or "A guest". A Space Manager can switch the option to hide off for the whole space, and people are told when they check in.
- The person is a member rather than a guest, and is not below the age of majority.
- Their profile can be read by the viewer, as described in [The global member profile](member-profile.md).

A person's contact details, history and project or event titles are never shown. The "Presence display" settings (where names are switched on or off) live in the space's settings; see [Let people check in by location](presence-check-in.md).

## Choose what the page and screens show

Open **Settings, Display screens**. There are two places to choose.

**The public page** (the *Public page sections* block): tick the sections you want, drag them (or use the up and down buttons) into order, pick how private **Here now** is and how often the page refreshes. The sections are Here now, Machines now, Events calendar, **Public stats** and **Opening hours**. Public stats only ever shows the numbers your public stats page already publishes, with the same "fewer than 3" rule. A section still needs its own area to be on.

**Each screen**: the same list of sections plus **Announcement**, **Inventory highlights** and **Sponsors**, and these choices:

| Setting | Choices |
| --- | --- |
| **Layout** | *Rotating playlist* (one section at a time, with your own seconds for each slide), *Single panel* (the first section only) or *Grid* (all sections at once) |
| **Theme** | Dark (the original), Light, Solid black (for OLED panels), Space brand, or Space default (follows the look you set for the space) |
| **Who Here now shows** | *People who opened their profile, by name* (how it always worked), *First names only*, or *Counts only, no names*. A choice can only show **less** than the public page does, never more |
| **Refresh** | How often the screen asks for new data, 10 to 600 seconds |

Under each screen a **live preview** shows the screen at 1080p size with sample people and numbers (never real ones), so you can see the layout, theme, order and privacy before pressing **Save changes**. Every change is recorded in the audit log.

### Inventory highlights and sponsors (screens only)

| Section | Shown when | What it shows |
| --- | --- | --- |
| **Inventory highlights** | The public inventory page is open to visitors | Up to eight of your most-lent **public** items with their name, category, picture and availability. Availability follows each item's own public setting: an exact count only when the item allows showing one, otherwise a status such as **Available** or **Limited**, and nothing at all when the item hides its availability. Private and archived items, consumables, storage locations, boxes and QR codes never appear |
| **Sponsors** | The sponsors area is on and at least one sponsor is on the sponsor wall | The logos (or names) and tier of the sponsors on your public sponsor wall, the same ones visitors see. Contacts, amounts and perks never appear. Add logos and choose who is on the wall under Sponsors |

A screen that has chosen one of these sections but has nothing to show for it simply skips that slide.

## Turn it on

1. Make sure the areas you want to show are on: Presence for "Here now", Machines for "Machines now", Events for the calendar. See [Turn an area or add-on on or off safely](turn-areas-on-off.md).
2. For paired TV screens, also switch on **Display screens** (`presence.public_display`), which is off by default.

If an area is switched off, its section disappears from the page and the screen.

## Pair a TV or kiosk display

A display screen is a web page, so any browser on a TV, a mini PC or a tablet will do.

1. On the display device, open `/display` on your site. It shows a short **pairing code** and nothing else. A code is valid for 30 minutes, so pair soon after it appears.
2. In the staff console, open **Settings, Display screens**, type the code and press **Pair screen**.
3. Name the screen and choose its sections, order, layout and theme as described above. Seconds per slide are between 5 and 120.
4. For an announcement, type up to 280 characters; the Announcement panel shows it.
5. Press **Save changes**.

Changes reach the screen within about ten seconds. The list shows each screen as **Online** or **Offline**. **Unpair** stops a screen at once and it goes back to showing a new code.

### What a screen shows

- Only what a visitor who is not signed in could see, so people are named only if their profile is open to the web and they did not hide their presence.
- A dark layout that is easy to read in a dim room, with a slow drift so no part of the picture stays fixed (this avoids screen burn-in).
- The last data it received if the network drops, with a **Reconnecting** notice, and it catches up when the connection returns.

### Limits and records

Pairing codes are rate limited: one person can try about 30 codes an hour and a space about 30 wrong codes an hour, and every wrong code is recorded in the audit log. One network can have only a few screens waiting for a code at a time.

Paired screens count against the `paired_displays` limit, which has no cap unless the platform operator sets one. Pairing, changing and unpairing are recorded in the audit log. Paired screens are never carried when a space is moved to another server; the new server pairs its own.

## Screens without a code, and Anthias

A player that cannot type a pairing code (such as [Anthias](anthias.md) on a Raspberry Pi) uses **Make a screen link** instead of a code. The screen gets an address ending in `#k=...`. Anyone who has the address can see that screen, so treat it like a password. The address is shown once, when you make it or press **New address**; the list never shows it again, so copy it then. If you lose it, **New address** replaces it and the old one stops at once. The part after `#` is never sent to a web server, and the screen sends its secret in a request header to a fixed address, so it stays out of access logs. These screens need no sign-in, set no cookies, show no consent banner and are never sent to web analytics or session replay. See [Show your screens on Anthias](anthias.md).

### If your server logs are older than release 0.12.0

Before 0.12.0 a screen sent its secret in the request path, so access logs from that time may contain it. If anyone you do not trust can read those logs, press **New address** on each link screen (or **Unpair** and pair again for a code screen). Screens on 0.12.0 send the secret in an `Authorization: Display <secret>` header to `/api/v1/space-displays/state/`; the old path still answers for a short while and is blanked out of every log line.

## Check it worked

1. Open the space's public page signed out and confirm the sections you expect, and that people who hid their presence are only counted.
2. Pair a screen, wait about ten seconds and confirm the panels rotate at the speed you chose.
3. Unplug the screen's network for a minute. It should keep showing the last data with "Reconnecting".

## See also

- [Show your screens on Anthias](anthias.md)
- [Presence](../modules/presence.md)
- [Let people check in by location](presence-check-in.md)
- [The global member profile](member-profile.md)
