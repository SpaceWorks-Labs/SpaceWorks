"""Parity E-B3 routes (team handover, removal, organiser moderation, crew edit and reorder).

Every one is native: the member routes use the member session, the organiser routes the event grant
(`manage_team` / `manage_volunteers`) for THAT event. Classification grants no domain authority.
"""

EB3_ROUTES = (
    ('events-programme-member-team-handover', ('POST',), 'event'),
    ('events-programme-member-team-remove-member', ('POST',), 'event'),
    ('events-programme-member-team-decline-request', ('POST',), 'event'),
    ('events-programme-admin-team-rename', ('POST',), 'event'),
    ('events-programme-admin-team-move-member', ('POST',), 'event'),
    ('events-programme-admin-team-delete', ('POST',), 'event'),
    ('events-programme-admin-team-restore', ('POST',), 'event'),
    ('events-programme-admin-crew-detail', ('PATCH',), 'event'),
    ('events-programme-admin-crew-reorder', ('POST',), 'event'),
)
EB3_NATIVE_DECISIONS = {name: "native" for name, methods, target in EB3_ROUTES}
