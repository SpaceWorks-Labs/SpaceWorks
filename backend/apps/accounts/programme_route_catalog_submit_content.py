"""Lane r2-submit-content routes (#177-#180) and their native-app decisions (#173).

Composed into `programme_route_catalog.ROUTES` like L21b's rows; classification grants no domain
authority. Every route is NATIVE: an event-role grant (#173) reaches the event-targeted admin routes
of ITS event, and the hackathon-manager check still runs inside each command.
"""

SUBMIT_CONTENT_ROUTES = (
    ('events-programme-admin-submission-stages', ('GET', 'HEAD', 'PUT'), 'event'),
    ('events-programme-admin-submission-stage-shortlist', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-submission-stage-shortlist-preview', ('POST',), 'event'),
    ('events-programme-admin-submission-stage-shortlist-apply', ('POST',), 'event'),
    ('events-programme-admin-submission-stage-shortlist-publish', ('POST',), 'event'),
    ('events-programme-admin-submission-stage-shortlist-promote', ('POST',), 'event'),
    ('events-programme-admin-submission-stage-extensions', ('POST',), 'event'),
    ('events-programme-admin-submission-stage-triage', ('POST',), 'event'),
)
SUBMIT_CONTENT_NATIVE_DECISIONS = {name: "native" for name, methods, target in SUBMIT_CONTENT_ROUTES}
