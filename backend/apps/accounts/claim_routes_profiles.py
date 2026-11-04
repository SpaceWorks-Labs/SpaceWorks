"""Public metadata ignores claim tokens; a walk-in proof cannot claim a global name."""
from .claim_route_types import AnonymousRead, Allowed, ID, ReadOnly, Refused, RowOwnership

PROFILE_CLAIM_ROUTES = {
    **{("member-event-history", method): Refused(
        "Event history can include foreign-hosted registrations.",
        ownership=RowOwnership.MIXED_REFUSED,
    ) for method in ("GET", "HEAD")},
    ("member-event-history", "OPTIONS"): AnonymousRead(),
    ("member-event-speaker-claim", "POST"): Refused(
        "Speaker invitations require a full account session."),
    ("member-event-speaker-claim", "OPTIONS"): AnonymousRead(),
    **{(name, method): AnonymousRead() for name in (
        "public-profile", "public-profile-activity", "public-profile-events", "public-profile-projects", "public-profile-github",
    ) for method in ("GET", "HEAD", "OPTIONS")},
    **{("member-profile-handle", method): Refused(
        "A global public handle requires a full account session.") for method in ("POST", "DELETE")},
    ("member-profile-handle", "OPTIONS"): AnonymousRead(),
    ("member-profile", "PATCH"): Allowed(tenant=ID, audited=True, ownership=RowOwnership.LOCALLY_FILTERED),
    **{(name, method): ReadOnly(tenant=ID) for name in (
        "member-profile-timeline", "member-profile-timeline-detail",
    ) for method in ("GET", "HEAD")},
    ("member-profile-timeline", "POST"): Allowed(tenant=ID, audited=True),
    ("member-profile-timeline-detail", "PATCH"): Allowed(tenant=ID, audited=True),
    ("member-profile-timeline-detail", "DELETE"): Allowed(tenant=ID, audited=True),
    **{(name, "OPTIONS"): AnonymousRead() for name in (
        "member-profile-timeline", "member-profile-timeline-detail",
    )},
}
