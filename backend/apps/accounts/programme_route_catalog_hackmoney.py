"""Hack-money lane (#180) programme routes and the native-app decision for each (#173).

Composed into `programme_route_catalog.ROUTES` like L21a/L21b; classification grants no domain
authority. Every route is NATIVE: an event-role grant reaches the event-targeted admin routes of
ITS event; member routes work on any member grant.
"""

HACKMONEY_ROUTES = (
    ('events-programme-admin-team-charges-missing', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-team-charges-raise', ('POST',), 'event'),
)
NATIVE = "native"
HACKMONEY_NATIVE_DECISIONS = {name: NATIVE for name, methods, target in HACKMONEY_ROUTES}
