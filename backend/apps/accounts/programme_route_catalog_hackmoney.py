"""Hack-money lane (#180) programme routes and the native-app decision for each (#173).

Composed into `programme_route_catalog.ROUTES` like L21a/L21b; classification grants no domain
authority. Every route is NATIVE: an event-role grant reaches the event-targeted admin routes of
ITS event; member routes work on any member grant.
"""

HACKMONEY_ROUTES = (
    ('events-programme-admin-team-charges-missing', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-team-charges-raise', ('POST',), 'event'),
    # G3-G6/G8/G16 and #181 G7: prize splits, claims, outcomes and the prize pool.
    ('events-programme-admin-prize-split', ('POST',), 'event'),
    ('events-programme-admin-prize-fulfil', ('POST',), 'event'),
    ('events-programme-admin-prize-forfeit', ('POST',), 'event'),
    ('events-programme-admin-prize-outcomes', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-prize-recovery-resolve', ('POST',), 'event'),
    ('events-programme-admin-prize-claims', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-prize-claim-verify', ('POST',), 'event'),
    ('events-programme-admin-prize-claim-reveal', ('POST',), 'event'),
    ('events-programme-admin-prize-pool', ('GET', 'HEAD'), 'event'),
    ('events-programme-member-prize-split', ('POST',), 'event'),
    ('events-programme-member-prize-share-confirm', ('POST',), 'event'),
    ('events-programme-member-prize-share-decline', ('POST',), 'event'),
    ('events-programme-member-prize-claim', ('POST',), 'event'),
    ('events-programme-member-prize-claim-remove', ('POST',), 'event'),
    ('events-programme-member-my-prizes', ('GET', 'HEAD'), 'tenant'),
    ('events-programme-public-prizes', ('GET', 'HEAD'), 'public_event'),
)
NATIVE = "native"
HACKMONEY_NATIVE_DECISIONS = {name: NATIVE for name, methods, target in HACKMONEY_ROUTES}
