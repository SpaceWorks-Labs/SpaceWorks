"""Which capability opens the admission engine (#128 C-32).

One engine serves hackathons and any one-off event: `events.hackathons` keeps opening it
with teams, submissions and judging around it, and `events.applications` opens the same
application, review and offer flow on an event without those. Neither switch is an
authorization fallback; every route still checks event authority.
"""
from apps.makerspaces.platform import feature_enabled

HACKATHONS = "events.hackathons"
APPLICATIONS = "events.applications"


def hackathon_enabled(makerspace):
    return feature_enabled(makerspace, HACKATHONS)


def admission_enabled(makerspace):
    return hackathon_enabled(makerspace) or feature_enabled(makerspace, APPLICATIONS)


def applications_only(makerspace):
    """The form-and-review flow without hackathon teams, finder or submissions."""
    return feature_enabled(makerspace, APPLICATIONS) and not hackathon_enabled(makerspace)
