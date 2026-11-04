"""Lane L21b programme routes and the native-app decision for each (#173).

Composed into `programme_route_catalog.ROUTES`, like L21a's rows; classification grants no domain
authority. Every L21b route is NATIVE: an event-role grant (#173) reaches the event-targeted admin
routes of ITS event; member routes work on any member grant; staff routes still need a staff grant.
"""

L21B_ROUTES = (
    ('events-programme-admin-finalists-list', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-finalists-preview', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-finalists-apply', ('POST',), 'event'),
    ('events-programme-admin-finalists-publish', ('POST',), 'event'),
    ('events-programme-admin-judging-rounds-progress', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-judging-rounds-next-project', ('POST',), 'event'),
    ('events-programme-admin-programme-options', ('GET', 'HEAD', 'PATCH'), 'event'),
    ('events-programme-admin-results-send-email', ('POST',), 'event'),
    ('events-programme-admin-prize-payouts', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-admin-prize-payouts-reverse', ('POST',), 'event'),
    ('events-programme-admin-staff-list', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-staff-list-export', ('GET', 'HEAD'), 'event'),
    ('events-programme-member-teams-charges', ('GET', 'HEAD'), 'event'),
    ('events-programme-member-teams-entry-fee', ('POST',), 'event'),
)
NATIVE = "native"
L21B_NATIVE_DECISIONS = {name: NATIVE for name, methods, target in L21B_ROUTES}
