---
title: Show your screens on Anthias
group: How-to guides
order: 251
summary: Run your display screens on a Raspberry Pi with Anthias (Screenly OSE), either by adding the address by hand or by letting SpaceWorks create, update and remove the web assets for you.
---

# Show your screens on Anthias

[Anthias](https://anthias.screenly.io/) (formerly Screenly OSE) is free digital-signage software for a Raspberry Pi. It plays a list of *assets* (images, videos and web pages) on a screen. A SpaceWorks display screen is a web page, so it is one web asset. You can add it by hand, or register the player in SpaceWorks and let SpaceWorks keep the assets in step.

Before you start, set up the screens themselves: [Public space page and display screens](display-screens.md).

## What you need

- A Raspberry Pi running Anthias, on the same network as your computer.
- The **Display screens** area on (`presence.public_display`). For the automatic option, also switch on **Send display screens to Anthias** (`display.anthias_push`, off by default).
- A Space Manager account.

## Set up Anthias on a Pi

1. Follow the install steps on the Anthias site for your Pi model and flash the card.
2. Connect the Pi to a TV by HDMI and to your network. The Anthias web page on the Pi (its IP address, for example `http://192.168.1.20`) is where you manage assets.
3. In Anthias, set the screen resolution to the TV's (1080p or 4K). Anthias shows web pages in an embedded browser (Qt WebEngine). SpaceWorks screens scale to the width of the screen and work at both sizes.

## Option A: add the address by hand

1. In SpaceWorks open **Settings, Display screens** and press **Make a screen link**. Name it, choose the sections and layout, and save.
2. Under the new screen, **Use with Anthias** shows its address, a **Copy address** button, a QR code and a **suggested duration** (one full pass of the playlist, so no slide is cut short).
3. In Anthias press **Add Asset**, choose **URL**, paste the address, set **Duration** to the suggested seconds, and save.

The address ends in `#k=` and a long secret. Anyone with it can see that screen, so share it like a password. It is shown only once, right after you make it or press **New address**, so copy it then. **New address** replaces it; the old one stops working at once and a hand-added asset needs the new address. If your server logs date from before release 0.12.0, press **New address** on each screen once: older screens sent the secret in the request path, where an access log could keep it.

## Option B: let SpaceWorks manage the assets

### Register a player

1. Open **Settings, Display screens** and find **Anthias players**.
2. Enter a **name** and the **address** of the Pi (`http://192.168.1.20`, no path). If you turned on a username and password in Anthias, enter them. The password is stored encrypted and is never shown again.
3. Press **Add player**, then **Test connection**. A green line shows the Anthias version and which API it uses.

You can register up to ten players per space.

### Choose what each player shows

Under each screen that has a link, tick the players that should show it. SpaceWorks then:

- **creates** one web asset per screen on each ticked player (name `SpaceWorks: <screen name> (#<id>)`, because Anthias's older API refuses two assets with the same name, the screen's address, the suggested duration, enabled, in screen order);
- **updates** that same asset when you change the screen's name, layout or slide seconds, so you never get duplicates;
- **deletes** the asset when you untick the player, unpair the screen or remove the player.

Changes sync on their own within a minute or so. **Sync now** on a player does it immediately. Each player shows its last result: *In sync*, *Not synced yet* or an *Error* with the reason, plus the time of the last sync. If someone deletes the asset on the player, the next sync recreates it. Every test, sync and change is in the audit log.

If a sync fails because the player was unreachable or slow, SpaceWorks retries a few times with longer waits (30 seconds, 1 minute, 2, 4) and then leaves the error on the player for you to see.

### Which Anthias versions work

SpaceWorks tries the current API (`/api/v2`) first and falls back to the older `/api/v1.2`, then uses whichever the player answers. **Test connection** shows which one it found. Only the v2 API reports the Anthias version, so a player on v1.2 shows the API but no version.

## Network and safety rules

- Only `http://` and `https://` addresses are accepted.
- Players usually live on your local network, so private addresses such as `192.168.x.x` and `10.x.x.x` are **allowed by default on a self-hosted SpaceWorks**. A managed (hosted) SpaceWorks allows only public addresses unless its operator sets `ANTHIAS_ALLOW_PRIVATE_HOSTS=true`; a self-host operator can restrict to public addresses with `ANTHIAS_ALLOW_PRIVATE_HOSTS=false`.
- Loopback addresses, link-local addresses, cloud metadata addresses (such as `169.254.169.254` and `100.100.100.200`) and the SpaceWorks server's **own service networks** (the Docker network its database, storage and dashboards sit on, plus any network listed in `OUTBOUND_BLOCKED_NETWORKS`) are **always refused**, even when private addresses are allowed.
- If you change a player's address, its saved password is cleared: type it again (with the new address, in the same save). The password is never sent to a new address you have not confirmed it for.
- SpaceWorks must be able to reach the Pi. A SpaceWorks server in the cloud cannot reach a Pi on your home network; in that case use Option A, or run SpaceWorks on the same network.
- SpaceWorks looks the player's name up once per call, checks the answer, and connects to exactly that address, so the name cannot be pointed somewhere else halfway through.
- Calls have short time limits (and one overall limit, so a slow answer cannot hold the server), read at most 1 MB, never follow redirects and never log the password.
- **Test connection** says *connected*, or *the player did not answer as expected* for anything the player did (refused, timed out, wrong password, not Anthias). It does not say which, so the test cannot be used to probe what else is on the network. Only problems with the address itself (not allowed, name not found) are told apart. Test and Sync now are limited to 20 calls a minute per person.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| *The player did not answer as expected* | Check, in order: the Pi is on; the address and port (open it in a browser from the same network as the SpaceWorks server); the username and password in Anthias's settings and in SpaceWorks (edit the player and type the password again). |
| *The player could not be reached* (older messages) | Check the address and that the Pi is on. Open the address in a browser from the same network as the SpaceWorks server. |
| *The player refused the username or password* (Anthias answers a missing or wrong login with a redirect to its login page) | Re-enter the credentials in Anthias's settings and in SpaceWorks (edit the player and type the password again). |
| *That host does not look like Anthias* | The address answered but has no Anthias API. Check the port. |
| *That address is not allowed* | The address is loopback, link-local or a cloud metadata address. Use the Pi's LAN address. |
| *This deployment does not allow players on a private network* | Ask your platform operator, or use Option A. |
| *A screen has no address yet* | Only screens made with **Make a screen link** can be sent. A code-paired screen cannot. |
| The page is blank or stuck on "Reconnecting" | The Pi cannot reach SpaceWorks. After the network returns the page reloads itself. |
| The screen says its address is no longer valid | The address was replaced or the screen was unpaired. Press **Sync now**, or paste the new address. |
| Slides get cut off | Set the asset's duration to at least the suggested seconds. |

## Switching it off

Switching **Send display screens to Anthias** off stops all syncing and hides the players, but keeps them. A platform operator can then purge the players, their stored passwords and the asset links in one step. Assets already on a Pi are not removed by a purge; delete them in Anthias.

## How this was checked against Anthias

The client follows the Anthias source, repository `Screenly/Anthias`, commit `6a8202b47a0b39039ed5d17cac8adde9b4a9aad8`:

- `src/anthias_server/django_project/urls.py` (API mounted at `/api/`) and `src/anthias_server/api/urls/v2.py`, `v1_2.py` (routes `v2/assets`, `v2/assets/<id>`, `v2/info`, `v1.2/assets`, `v1.2/assets/<id>`).
- `src/anthias_server/api/serializers/v2.py` and `v1_2.py` (field names and types: v2 uses booleans and an integer duration, v1.2 uses 0/1 integers and a string duration; new assets answer with `asset_id`).
- `src/anthias_server/api/views/v2.py`, `v1_2.py`, `mixins.py` (create answers 201, update 200, delete 204, unknown asset 404; `v2/info` carries `anthias_version`).
- `src/anthias_server/lib/auth.py` and `website/content/api.md` (a fresh install has no authentication; once on, HTTP Basic is used and an unauthenticated call is redirected to the login page instead of returning 401).

## Privacy

A screen address needs no sign-in and sets no cookies. These pages show no consent banner and are never sent to web analytics or session replay. What a screen shows follows the privacy choice you made for it (see [Public space page and display screens](display-screens.md)).

## See also

- [Public space page and display screens](display-screens.md)
- [Turn an area or add-on on or off safely](turn-areas-on-off.md)
