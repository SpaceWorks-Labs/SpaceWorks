"""Lane r2-peoples-choice routes (#181 S3) and the native-app decision for each (#173).

Composed into `programme_route_catalog.ROUTES`, like L21b's rows; classification grants no domain
authority. Every route is NATIVE: an event-role grant (#173) reaches the event-targeted admin routes
of ITS event; the member routes work on any member grant; the public read is anonymous.
"""

PEOPLES_CHOICE_ROUTES = (
    ('events-programme-admin-peoples-choice', ('GET', 'HEAD', 'PATCH'), 'event'),
    ('events-programme-admin-peoples-choice-standings', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-peoples-choice-publish', ('POST',), 'event'),
    ('events-programme-admin-peoples-choice-votes', ('GET', 'HEAD'), 'event'),
    ('events-programme-admin-peoples-choice-vote-void', ('POST',), 'event'),
    ('events-programme-admin-peoples-choice-payouts', ('GET', 'HEAD', 'POST'), 'event'),
    ('events-programme-member-peoples-choice', ('GET', 'HEAD'), 'event'),
    ('events-programme-member-peoples-choice-vote', ('POST',), 'event'),
    ('events-programme-public-peoples-choice', ('GET', 'HEAD'), 'public_event'),
)
NATIVE = "native"
PEOPLES_CHOICE_NATIVE_DECISIONS = {name: NATIVE for name, methods, target in PEOPLES_CHOICE_ROUTES}
