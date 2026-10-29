"""Release-2 lane L1: the public event surface (#21 gaps 10/12, #71, #73, #77, #95).

Every switch is off by default and keeps its data when turned off (#95, #128 C-8):

* `events.short_links` -- `/e/<7-char code>` aliases and their PII-free daily visit count;
* `events.online_delivery` -- online/hybrid events and the join link released only to
  confirmed registrants;
* `public_site.closed_notice` -- the Space Manager's "closed for now" banner on the public
  page (#77; no lifecycle state). Parentless, like `presence.geofence`: the public page is
  `Makerspace.public_site_enabled`, not a module key, and #97 forbids a new module.

`events.embed` already exists (yuyu parity); L1's styled card reuses that switch and adds
the per-space `EventEmbedPolicy` allow-list (`events/embed_policy.py`).
"""


def definitions(feature):
    return (
        feature(
            "events.short_links", "events", "Event short links",
            "Short /e/<code> links that follow the event; regenerate retires the old code. "
            "Visits are counted as one number per day, never who visited.",
        ),
        feature(
            "events.online_delivery", "events", "Online and hybrid events",
            "Mark events online or hybrid; the join link is shown only to confirmed registrants.",
        ),
        feature(
            "public_site.closed_notice", None, "Closed-for-now banner",
            "Show a short notice and an optional reopening date on the public page.",
        ),
    )
