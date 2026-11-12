"""Public metadata ignores claim tokens; a walk-in proof cannot claim a global name."""
from django.utils.translation import gettext_noop
from .claim_route_types import AnonymousRead, Allowed, ID, ReadOnly, Refused, RowOwnership

PROFILE_CLAIM_ROUTES = {
    **{("member-event-history", method): Refused(
        gettext_noop("Event history can include foreign-hosted registrations."),
        ownership=RowOwnership.MIXED_REFUSED,
    ) for method in ("GET", "HEAD")},
    ("member-event-history", "OPTIONS"): AnonymousRead(),
    ("member-event-speaker-claim", "POST"): Refused(
        gettext_noop("Speaker invitations require a full account session.")),
    ("member-event-speaker-claim", "OPTIONS"): AnonymousRead(),
    **{(name, method): AnonymousRead() for name in (
        "handle-check", "public-profile", "public-profile-activity", "public-profile-events", "public-profile-projects", "public-profile-github",
    ) for method in ("GET", "HEAD", "OPTIONS")},
    **{("member-profile-handle", method): Refused(
        gettext_noop("A global public handle requires a full account session.")) for method in ("POST", "DELETE")},
    ("member-profile-handle", "OPTIONS"): AnonymousRead(),
    ("member-profile", "PATCH"): Refused(gettext_noop("The global profile requires a full account session.")),
    **{(name, method): ReadOnly(tenant=ID) for name in (
        "member-profile-timeline", "member-profile-timeline-detail",
    ) for method in ("GET", "HEAD")},
    ("member-profile-timeline", "POST"): Refused(gettext_noop("The global profile requires a full account session.")),
    ("member-profile-timeline-detail", "PATCH"): Refused(gettext_noop("The global profile requires a full account session.")),
    ("member-profile-timeline-detail", "DELETE"): Refused(gettext_noop("The global profile requires a full account session.")),
    **{(name, "OPTIONS"): AnonymousRead() for name in (
        "member-profile-timeline", "member-profile-timeline-detail",
    )},
    # Self-reported achievements follow the timeline rules (decision 302c).
    **{(name, method): ReadOnly(tenant=ID) for name in (
        "member-profile-achievements", "member-profile-achievement-detail",
    ) for method in ("GET", "HEAD")},
    ("member-profile-achievements", "POST"): Refused(gettext_noop("The global profile requires a full account session.")),
    ("member-profile-achievement-detail", "PATCH"): Refused(gettext_noop("The global profile requires a full account session.")),
    ("member-profile-achievement-detail", "DELETE"): Refused(gettext_noop("The global profile requires a full account session.")),
    **{(name, "OPTIONS"): AnonymousRead() for name in (
        "member-profile-achievements", "member-profile-achievement-detail", "member-profile-project-import",
    )},
    # Hackathon submissions can belong to any space the account took part in (decision 302d).
    **{("member-profile-project-import", method): Refused(
        gettext_noop("Importing a submission reads events hosted by other spaces."),
        ownership=RowOwnership.MIXED_REFUSED,
    ) for method in ("GET", "HEAD", "POST")},
}

# The account-level profile (decisions 304/305) is global: a claim session is scoped to ONE tenant,
# so none of these routes is reachable from one. Every method refuses; OPTIONS stays public.
_GLOBAL_PROFILE_METHODS = {
    "member-global-profile": ("GET", "HEAD", "PUT", "PATCH"),
    "member-global-profile-handle": ("POST", "DELETE"),
    "member-global-profile-image": ("POST", "PUT", "DELETE"),
    "member-global-profile-timeline": ("GET", "HEAD", "POST"),
    "member-global-profile-timeline-detail": ("GET", "HEAD", "PATCH", "DELETE"),
    "member-global-profile-achievements": ("GET", "HEAD", "POST"),
    "member-global-profile-achievement-detail": ("PATCH", "DELETE"),
    "member-global-profile-project-import": ("GET", "HEAD", "POST"),
    "profile-by-account": ("GET", "HEAD"),
}
for _name, _methods in _GLOBAL_PROFILE_METHODS.items():
    for _method in _methods:
        PROFILE_CLAIM_ROUTES[(_name, _method)] = Refused(
            gettext_noop("The global profile requires a full account session."))
    PROFILE_CLAIM_ROUTES[(_name, "OPTIONS")] = AnonymousRead()
