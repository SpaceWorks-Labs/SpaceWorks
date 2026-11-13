---
title: Let people check in by location
group: How-to guides
order: 180
summary: Configure a geofence for self check-in, choose privacy for the who's-in display, and fall back to staff check-in.
---

# Let people check in by location

Presence records who is on site for a limited time and can show a public "who's in" screen. Self check-in works only when the person's browser reports a location **inside a radius you configure**.

## Before you start

- The **Presence** add-on is on for the space (**Areas & add-ons**). It is independent and needs nothing else.
- You know the space's latitude and longitude.
- The site is served over HTTPS (or `localhost`); browsers refuse location access otherwise.

## Steps

1. Open **Settings > People > Membership** (the section shows while Membership or Presence is on) and find **Presence geofence**.
2. Tick **Enable geofence**, enter the **Latitude**, **Longitude** and **Radius (metres)**, and save. Coordinates are not stored against people.
3. Open **Settings > People > Presence** (Space Manager) to set **Presence display**:
   - **Show names**: off means everyone appears as "A member" or "A guest" with no project or event titles.
   - **Let people hide their name**: when on, anyone can appear anonymously.
4. Check the screen at `/m/<slug>/now`. It shows current rows only and never shows contact details, coordinates or history.

## Status and expiry

A check-in has a status (working, visiting, attending an event or guest) and expires after a preset (1, 2, 3 or 4 hours by default). Expiry sends a personal renewal notice.

> **Warning** GPS can be spoofed. Without a configured, enabled geofence, self check-in is unavailable. Authorised staff can always check in members and walk-ins at the desk or kiosk without a location, which is the reliable alternative.

## Related behaviour

- Booking in advance never requires presence.
- Public project and event titles on the display need their own live visibility settings.
- Turning the add-on off keeps history; only a purge deletes it.

## See also

- [Module guide](../MODULES.md#presence)
- [Turn an area on or off safely](turn-areas-on-off.md)
