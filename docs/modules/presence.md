---
title: Presence
group: Areas & modules
order: 35
summary: Time-limited check-in, who is here now on the public page, and paired TV or kiosk display screens.
---

# Presence

Presence records who is physically at the space, for a limited time. It is an independent module and is off by default. Check-in is by location (see the membership page for the geofence) or by staff at the desk.

## What it does and who uses it

- Members and guest-pass holders check in for a preset time (1 to 4 hours) and can renew or leave early. Staff can check people in and out.
- The public page can show **Here now**, and a paired screen can show it on a wall.
- Privacy is the member's choice first, the space's second: a member can hide their presence, and a Space Manager can switch names off for the whole space.

## Switching it on and off

- Module: `presence`. Features: `presence.geofence` (on) and `presence.public_display` (off).
- Switched off, the sections and screens disappear and their routes answer 404. Data is kept.

## Here now on the public page

A person appears as a card (name, picture, headline, status and a few skills) only when the space shows names, they did not hide their presence, they are a member (not a guest) and not under the age of majority, and their account profile can be read by the viewer.

| Viewer | Who is named |
| --- | --- |
| Not signed in | People whose profile is open to the web |
| Signed in | People with a visible profile |
| Anyone | Everyone else is counted ("+ 7 more here"), never named |

## Display screens

Full steps are in [Public space page and display screens](../how-to/display-screens.md).

1. Turn on **Display screens** for the space.
2. Open `/display` on the TV or kiosk browser. It shows a short code.
3. In **Settings, Display screens**, enter the code, choose the panels (here now, events calendar, machines now, announcement) and the seconds per panel.
4. Changes reach the screen within about ten seconds. **Unpair** stops it at once.

A screen shows only what a visitor who is not signed in can see. It uses a dark, burn-in-safe layout, keeps the last data when the network drops and says "Reconnecting". Paired screens count against the `paired_displays` limit (none unless the platform sets one). Claiming, changing and unpairing are audited.

## Notifications it sends

Check-in expiry reminders to the member, in-app by default.

## Data kept and purged

Presence sessions are short-lived and are not carried in a tenant move; paired screens are never carried (the target pairs its own). A purge of the module deletes sessions, preferences, settings and display screens.

## Decisions

Decision: public pages show Here now, Machines now and an events calendar, and a space can run paired display screens. Decision: the profile visibility rules in [Memberships](memberships.md#the-global-member-profile) decide who is named. Setup steps: [Pair a display screen](../how-to/display-screens.md).
