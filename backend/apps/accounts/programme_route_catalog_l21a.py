"""Lane L21a programme routes and the native-app decision for each (#173).

Kept beside `programme_route_catalog.py`, which composes these rows into its literal
ROUTES inventory; classification still grants no domain authority.
"""

# Release 2 L21a: review stages, the panel workspace, participation switches, attendance
# confirmation, re-accept, crew and check-in lists.
L21A_ROUTES = (
    ('events-programme-admin-application-stages', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-admin-application-stage-detail', ('PATCH',), 'event'),
    ('events-programme-admin-application-stage-panel', ('PUT',), 'event'),
    ('events-programme-admin-application-stage-assignment-preview', ('POST',), 'event'),
    ('events-programme-admin-application-stage-assignment-apply', ('POST',), 'event'),
    ('events-programme-admin-application-stage-progress', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-my-application-reviews', ('GET', 'HEAD'), 'account'),
    ('events-programme-admin-application-stage-my-reviews', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-application-stage-review-submit', ('POST',), 'event'),
    ('events-programme-admin-participation-settings', ('GET', 'HEAD', 'PATCH'), 'event'),
    ('events-programme-admin-attendance-confirmation', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-admin-registration-reaccept', ('POST',), 'event'),
    ('events-programme-admin-crew', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-admin-crew-catering', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-crew-decide', ('POST',), 'event'),
    ('events-programme-admin-crew-remove', ('POST',), 'event'),
    ('events-programme-admin-checkin-lists', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-admin-checkin-list-detail', ('PATCH',), 'event'),
    ('events-programme-admin-checkin-list-lookup', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-checkin-list-scan', ('POST',), 'event'),
    ('events-programme-admin-checkin-list-reorder', ('POST',), 'event'),
    ('events-programme-admin-checkin-list-scan-undo', ('POST',), 'event'),
    ('events-programme-member-attendance', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-member-crew-signup', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-member-crew-withdraw', ('POST',), 'event'),
    ('events-programme-public-crew', ('GET', 'HEAD'), 'public_event'),
)
# The native-app decision for each L21a route (#173). L21b's native event-role grant opens the
# crew desk and the per-event review-panel workspace to an ``event`` grant for THAT event (member
# grants still refuse delegated authority, #162(2)). Only the cross-event "my application reviews"
# list stays web-only: an event grant is limited to one event and that list spans every event.
WEB_ONLY = "web_only"
NATIVE = "native"
DESKS = ('events-programme-admin-my-application-reviews',)
NATIVE_DECISIONS = {name: WEB_ONLY if name in DESKS else NATIVE for name, methods, target in L21A_ROUTES}
NATIVE_WEB_ONLY = frozenset(name for name, decision in NATIVE_DECISIONS.items() if decision == WEB_ONLY)
