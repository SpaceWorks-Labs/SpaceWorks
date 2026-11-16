"""Parity E-B4 programme routes and the native-app decision for each (#173).

Composed into `programme_route_catalog.ROUTES`; classification grants no domain authority. All three are
event-targeted staff routes and work for an event-role grant on THEIR event.
"""

E_B4_ROUTES = (
    ('events-programme-admin-scores-export', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-results-unpublish', ('POST',), 'event'),
    ('events-programme-admin-submissions-reinstate', ('POST',), 'event'),
)
E_B4_NATIVE_DECISIONS = {name: "native" for name, methods, target in E_B4_ROUTES}
