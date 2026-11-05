"""L21b capability gates. Off means the route does not exist (404); data is kept for when it returns."""

from django.http import Http404

from apps.makerspaces.platform import feature_enabled

FINALISTS = "events.finalists"
PRIZE_PAYOUTS = "events.prize_payouts"
ENTRY_FEES = "events.entry_fees"
PAID_TEAMS = "events.paid_teams"
SAVED_VIEWS = "events.saved_views"
GALLERY_SEARCH = "events.gallery_search"


def enabled(makerspace, key):
    return feature_enabled(makerspace, key)


def require_capability(event, key):
    if not feature_enabled(event.makerspace, key):
        raise Http404
