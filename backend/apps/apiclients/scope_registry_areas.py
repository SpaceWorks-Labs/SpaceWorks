"""Per-area public scopes: least-privilege slices of `public:read` / `public:write`.

Every registry entry that a public scope can reach belongs to exactly one AREA. The area
adds one narrower scope to the entry -- `public:<area>:read` on a read entry,
`public:<area>:write` on a write entry -- so an external system can be granted, say,
the catalogue and nothing else. `public:read`, `public:write` and `public:*` keep
authorizing exactly what they did; an area scope only ever narrows.

`area_for` is an explicit lookup, never a guess from the name: a public route that is
not listed here makes the registry build raise, so a new route cannot quietly end up
with no area (and therefore unreachable by an area-scoped client, or worse, filed under
the wrong one). Entries no scope reaches (`frozenset()` -- bearer links, a buyer's own
checkout) and the operator-only staff reads are not public and carry no area.

PEER clients (another space's backend reading this one, docs/api-guide.md) may hold
only the read scopes of `PEER_AREAS`: the public catalogue, events and stats.
"""

AREAS = {
    "catalogue": ("Catalogue", "The public inventory, categories, machines and the list of spaces."),
    "events": ("Events", "Public event pages, calendars, tickets, programme pages and registrations."),
    "stats": ("Stats", "The space's public statistics."),
    "bookings": ("Bookings", "Bookable spaces, availability, booking websites and a booker's own links."),
    "pages": ("Pages and profiles", "Space and organization pages, and public maker profiles."),
    "requests": ("Hardware requests", "Borrow requests, their status, and self-checkout of QR tools."),
    "machine_service": ("Machine jobs", "Machine-job and 3D-print requests, their uploads and status."),
    "memberships": ("Memberships", "Membership plans, admission, invitations and join requests."),
    "presence": ("Presence", "Who is in now, and a visitor's own check-in."),
    "shop": ("Shop", "The public shop catalogue, quotes and orders."),
    "donations": ("Donations", "The donation page and sponsor walls."),
    "pricing": ("Pricing", "Price previews from the space's public prices."),
    "id_programmes": ("ID programmes", "Public ID-card programmes of an organization."),
    "repairs": ("Repairs", "Account-less issue reports for broken equipment."),
    "hosting": ("Hosting", "Requests to host a space on this platform."),
}
PEER_AREAS = frozenset({"catalogue", "events", "stats"})

_NAMES = {
    "catalogue": (
        "public-makerspaces", "v1:public-makerspaces", "public-inventory", "v1:public-inventory",
        "public-inventory-categories", "v1:public-inventory-categories", "public-inventory-detail",
        "v1:public-inventory-detail", "public-inventory-watch", "v1:public-inventory-watch",
        "public-machines", "public-machine-detail", "public-machine-details", "public-machine-intake",
        # #185: whether a listed space is paused (the SPA's paused page).
        "public-makerspace-availability",
    ),
    "events": (
        "public-event-code", "public-event-short-code", "public-event-website", "public-event-website-section",
        "public-event-website-session", "public-event-website-image", "public-event-website-schedule",
        "public-event-website-speaker", "public-event-venue", "public-event-organization-eligibility",
        "public-event-detail", "public-event-share-image", "public-event-list", "public-organization-events",
        "public-event-calendar", "public-event-calendar-feed", "public-event-register", "public-event-feedback",
        "public-event-ticket-shop", "public-listed-events-calendar", "public-shift-calendar-feed",
        "public-combined-calendar-feed",
    ),
    "stats": ("public-makerspace-stats", "v1:public-makerspace-stats"),
    "bookings": (
        "public-booking-resource", "public-booking-website", "public-booking-website-image",
        "member-booking-pass", "member-booking-confirmation", "member-booking-confirmation-png",
        "member-booking-calendar", "member-booking-rotate-checkin", "member-booking-reschedule",
        "member-booking-feed-settings", "public-booking-feed", "member-booking-list",
        "member-booking-cancel", "member-booking-checkout", "public-bookable-space-list",
        "public-space-availability", "public-booking-submit",
    ),
    "pages": (
        "public-page-handle", "public-makerspace-page", "public-makerspace-page-asset",
        "public-organization-page", "public-organization-page-asset", "public-organization-makerspaces",
        "public-organization-detail", "public-organization-directory", "public-profile", "public-profile-activity", "public-profile-events",
        "public-profile-projects", "public-profile-github",
    ),
    "requests": (
        "hardware_requests:request-submit", "hardware_requests:request-contact-code",
        "hardware_requests:public-tool-evidence-url", "hardware_requests:public-tool-checkout",
        "hardware_requests:public-tool-return", "hardware_requests:public-tool-checklist",
        "hardware_requests:request-status",
    ),
    "machine_service": (
        "public-machine-service-request-submit", "public-printer-service-queues", "public-printer-service-pools",
        "public-printer-service-upload", "public-printer-service-request", "public-printer-service-status",
        "public-machine-service-status", "public-machine-job-types", "public-machine-job-upload",
        "public-machine-job-submit",
    ),
    "memberships": (
        "public-membership-request", "public-membership-admission", "public-membership-plans",
        "public-membership-plan-detail", "public-membership-invite", "public-invitation-request",
        "public-day-passes", "public-member-units",
    ),
    "presence": (
        "presence-start", "presence-current", "presence-end", "public-presence-now", "presence-renew",
        "public-presence-here-now", "public-machines-now", "public-presence-now-config",
        "presence-projects", "presence-preferences",
    ),
    "shop": (
        "public-shop", "public-shop-products", "public-shop-product", "public-shop-order-status",
        "public-shop-quote", "public-shop-email-code", "public-shop-orders", "public-shop-event-offers",
    ),
    "donations": ("public-donation-page", "public-sponsor-wall", "public-event-sponsors"),
    "pricing": ("pricing-quote",),
    "id_programmes": ("public-organization-id-programmes", "public-id-programme"),
    "repairs": ("public-issue-report", "public-issue-photo-upload"),
    "hosting": (
        "public-hosting-request-submit", "public-hosting-request-open", "public-hosting-invitation-resolve",
        "public-hosting-invitation-submit", "public-hosting-request-resubmit",
    ),
}
_BY_NAME = {name: area for area, names in _NAMES.items() for name in names}
# Programme public pages (hackathon results, prizes, gallery, crew, volunteer postings) come
# from the closed programme route catalogue, which owns their names.
_PREFIXES = (("events-programme-public-", "events"),)


def area_for(view_name):
    """The area a public route belongs to, or None when it is not listed."""
    if view_name in _BY_NAME:
        return _BY_NAME[view_name]
    for prefix, area in _PREFIXES:
        if view_name.startswith(prefix):
            return area
    return None


def area_scope(area, access):
    return f"public:{area}:{access}"


PEER_SCOPES = frozenset(area_scope(area, "read") for area in PEER_AREAS)
