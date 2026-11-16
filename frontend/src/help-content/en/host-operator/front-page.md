---
title: Show or hide the SpaceWorks front page
summary: Keep the product page at your site's front page, or switch it off so your own space opens there.
order: 80
keywords: landing, front page, home page, product page, features, hub, apply-settings, HUB_LANDING_ENABLED
---
The product landing is at `/about` while enabled. Your front page shows it when there are no public spaces or the backend is unreachable; one public space opens that space's home, and several open the directory. You can switch the product landing off.

The landing and [Features](/features) carry the full catalogue formerly in the README: every module and what happens without it, feature switches, connections, integrations, free and paid operation, limits and public TV setup. Both reuse the app's module and feature definitions. [Docs](/docs) stays on your own domain at `<domain>/docs`; `docs/MODULES.md` remains the developer reference.

## Switch it

1. Connect to the server and go to the install folder.
2. Run `bash scripts/apply-settings.sh --landing off` to hide it, or `--landing on` to show it. Setup also asks this question when you first install, and the default is yes.
3. Open your front page in a private window. With the page off you see your space's home when exactly one public space exists, otherwise the spaces directory.
4. Open `/features`, `/docs` and `/spaces`. They work either way.

![Screenshot: the front page opening on the spaces directory](screenshot:ho-front-page)

Spaces on their own domain are never affected. The setting is `HUB_LANDING_ENABLED` in the environment reference.

> **Who can do this:** whoever runs the server.
