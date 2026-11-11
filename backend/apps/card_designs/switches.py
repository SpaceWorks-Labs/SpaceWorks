"""The per-space switches that govern each card surface (LANE-RULES §9, #95).

| Surface | Switch |
|---|---|
| member cards, their designs, jobs and public check | module `membership` |
| ID programmes | capability `membership.id_programmes` (and the app shipped) |
| event ID cards and their designs | capability `events.id_cards` |
| event ticket designs (X49) | capability `events.ticket_designs` |
| staff ID cards, their design and number scheme | module `membership` + capability `membership.staff_cards` |
| auto-issue a staff card when a staff role is granted | `membership.staff_cards_auto_issue` (needs the one above) |
| wallet passes | `membership.wallet_passes` / `events.wallet_passes` + the space's or the platform's credentials |

Off means no UI, 404 from the API and no scheduled work; the data is kept.
"""
from apps.makerspaces.platform import feature_enabled, module_enabled

MEMBERSHIP_PROGRAMMES = "membership.id_programmes"
EVENT_CARDS = "events.id_cards"
EVENT_TICKETS = "events.ticket_designs"
BADGE_DESIGNER = "events.badge_designer"
ROLE_BADGES = "events.role_badges"
CARD_NUMBERING = "membership.card_numbering"
TITLE_REISSUE = "membership.title_card_reissue"
DESK_PRINT = "membership.card_desk_print"
STAFF_CARDS = "membership.staff_cards"
STAFF_CARDS_AUTO = "membership.staff_cards_auto_issue"
WALLET = {"member_card": "membership.wallet_passes", "programme_card": "membership.wallet_passes",
          "event_card": "events.wallet_passes", "staff_card": "membership.wallet_passes"}


def programmes_on(makerspace):
    from apps.separability.tombstones import app_is_tombstoned
    return not app_is_tombstoned("id_programmes") and feature_enabled(makerspace, MEMBERSHIP_PROGRAMMES)


def event_cards_on(makerspace):
    return module_enabled(makerspace, "events") and feature_enabled(makerspace, EVENT_CARDS)


def badge_designer_on(makerspace):
    return event_cards_on(makerspace) and feature_enabled(makerspace, BADGE_DESIGNER)


def role_badges_on(makerspace):
    return event_cards_on(makerspace) and feature_enabled(makerspace, ROLE_BADGES)


def staff_cards_on(makerspace):
    return module_enabled(makerspace, "membership") and feature_enabled(makerspace, STAFF_CARDS)


def domain_on(makerspace, domain):
    if domain == "member_cards":
        return module_enabled(makerspace, "membership")
    if domain == "staff_cards":
        return staff_cards_on(makerspace)
    if domain == "id_programme":
        return programmes_on(makerspace)
    if domain == "event_ticket":
        return module_enabled(makerspace, "events") and feature_enabled(makerspace, EVENT_TICKETS)
    return event_cards_on(makerspace)


def scope_enabled(job):
    space = job.makerspace
    return {"member_cards": lambda: module_enabled(space, "membership"), "id_programme": lambda: programmes_on(space),
            "event": lambda: event_cards_on(space), "staff_cards": lambda: staff_cards_on(space)}[job.scope]()


def wallet_on(kind, makerspace):
    from .wallet.credentials import configured_platforms
    return bool(configured_platforms(makerspace)) and feature_enabled(makerspace, WALLET[kind])


# The switch each card holder kind lives behind, as scheduled-work sources (#183B).
HOLDER_SOURCES = {"member_card": "membership", "programme_card": MEMBERSHIP_PROGRAMMES, "event_card": EVENT_CARDS,
                  "staff_card": STAFF_CARDS}


def live_holder_q(*, wallet=False):
    """Rows (any holder-keyed model) whose card kind is switched on for their space.

    Scheduled card work filters with this so an off switch runs nothing and its rows
    never crowd the bounded batch; `wallet=True` also needs that kind's wallet switch.
    """
    from django.db.models import Q
    from apps.makerspaces.scheduled_scope import live_space_ids
    q = Q(pk__in=[])
    for kind, source in HOLDER_SOURCES.items():
        sources = (source, WALLET[kind]) if wallet else source
        q |= Q(**{f"{kind}__isnull": False, "makerspace_id__in": live_space_ids(sources)})
    return q
