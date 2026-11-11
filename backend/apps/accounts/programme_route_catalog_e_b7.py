"""Parity E-B7 programme routes and the native-app decision for each.

Both are cross-event insight reads (one space, or one organisation's hosted events), so they are classed
`tenant` (membership authority only, no event-grant delegation) and stay web-only. Classification grants no
domain authority; the views re-check it.
"""

E_B7_ROUTES = (
    ('events-programme-admin-space-insights', ('GET', 'HEAD'), 'tenant'),
    ('events-programme-admin-organization-insights', ('GET', 'HEAD'), 'tenant'),
)
E_B7_NATIVE_DECISIONS = {name: "web_only" for name, methods, target in E_B7_ROUTES}
