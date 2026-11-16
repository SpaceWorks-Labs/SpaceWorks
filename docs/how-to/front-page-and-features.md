---
title: The SpaceWorks front page and the Features page
group: How-to guides
order: 220
summary: What the product page at your site's front page shows, how the Features page is built, and how to switch the front page on or off.
---

# The SpaceWorks front page and the Features page

A SpaceWorks site opens on a **product page** at its front page (`/`). It explains what the software does and links to the docs, the public spaces on the server and the source code. A separate **Features** page (`/features`) lists every area and what it gives you. This page explains both and shows how to turn the front page off if your space wants its own home there.

## What visitors see

The front page is a single scrolling story, written in the app's own look in light and dark themes:

- **An opening scene** that stays in place while you scroll: the tagline lifts away, a preview of the staff console rises into view and the page moves on to the overview.
- **A sample loan told step by step**, next to a record that stays pinned and fills in as each step passes.
- **The areas** (inventory, machines, events, bookings, memberships, payments, the shop and more), **how it works**, **self-hosting**, **the open-source licence**, **the apps**, **the spaces on this server**, **the docs** and **common questions**. Each section fades in once as it arrives.
- A faint tiled pattern of the SpaceWorks symbol behind the opening and overview sections, kept low-contrast so text stays easy to read, and the mascot Patch as one decorative moment on some pages.

The scrolling effect is turned off, and the page reads as an ordinary static page, when the visitor prefers reduced motion or the screen is narrower than a tablet. Every section is still there and in the same order.

### Where the links go

The page links to three public repositories:

| Link | Where it points |
| --- | --- |
| Main project | `github.com/SpaceWorks-Labs/SpaceWorks` |
| Android app | `github.com/SpaceWorks-Labs/SpaceWorks-Android` |
| iOS app | `github.com/SpaceWorks-Labs/SpaceWorks-iOS` |

The apps section shows the native Android and iOS apps as released, each with a "Download from GitHub Releases" link (no app-store listings); the source repositories are linked from the open-source section and the footer. Everything also works in the browser, and members can add their member area to the home screen.

## The Features page

`/features` lists every area of SpaceWorks, grouped the way setup groups them: inventory, machines, events, bookings, memberships and ID cards, payments, the shop, reports, notifications, organizations and the platform. For each area it shows:

- a short plain description and three things you get;
- every module in the area, with whether it is **always on**, **on in a new setup** or **off until you turn it on**;
- every feature switch inside the area, in a collapsible list;
- a link to the matching page in the [areas and modules docs](../modules/index.md).

The module names and switches come straight from the app's own feature catalogue, so the page cannot drift from what the software really has. The Features page also lists ID cards (member cards, staff ID cards and event badges), because they are a feature like any other.

The Features page and the other public pages (`/docs`, `/spaces`, `/about`) work whether the front page is on or off.

## Switch the front page on or off

The front page is **on by default on every install**, self-hosted ones included. A space that wants its own home page at `/` can switch it off.

- **At install.** Setup asks "Show the SpaceWorks product page at your site's front page?" The default is yes, and quick setup keeps it on. See [Install and update](../install-and-update.md).
- **Later.** On the server, run `bash scripts/apply-settings.sh --landing off` (or `--landing on`). This changes the `HUB_LANDING_ENABLED` setting and applies it without touching your data. See the [environment reference](../environment-reference.md).

### What `/` shows when the front page is off

| Public spaces on this server | What `/` shows |
| --- | --- |
| Exactly one | That space's home page, the same page as `/m/<slug>` |
| Several, or none | The spaces directory (`/spaces`) |

A space on its own domain never showed the product page, so nothing changes for it.

## Check it worked

1. Open your site's front page in a private window.
2. With the front page on you should see the product story. With it off you should land on the space's home page or the spaces directory.
3. Open `/features`, `/docs` and `/spaces`. All three should load either way.

## See also

- [Install and update](../install-and-update.md)
- [Hosting environment settings](../hosting/environment.md)
- [Areas and modules overview](../modules/index.md)
