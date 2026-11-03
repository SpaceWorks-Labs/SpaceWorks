"""The per-space switches that govern each card surface (LANE-RULES §9, #95).

| Surface | Switch |
|---|---|
| member cards, their designs, jobs and public check | module `membership` |
| ID programmes | capability `membership.id_programmes` (and the app shipped) |
| event ID cards and their designs | capability `events.id_cards` |
| event ticket designs (X49) | capability `events.ticket_designs` |
| wallet passes | `membership.wallet_passes` / `events.wallet_passes` + platform credentials |

Off means no UI, 404/400 from the API and no scheduled work; the data is kept.
"""
from apps.makerspaces.platform import feature_enabled, module_enabled

MEMBERSHIP_PROGRAMMES = "membership.id_programmes"
EVENT_CARDS = "events.id_cards"
EVENT_TICKETS = "events.ticket_designs"
WALLET = {"member_card": "membership.wallet_passes", "programme_card": "membership.wallet_passes",
          "event_card": "events.wallet_passes"}


def programmes_on(makerspace):
    from apps.separability.tombstones import app_is_tombstoned
    return not app_is_tombstoned("id_programmes") and feature_enabled(makerspace, MEMBERSHIP_PROGRAMMES)


def event_cards_on(makerspace):
    return module_enabled(makerspace, "events") and feature_enabled(makerspace, EVENT_CARDS)


def domain_on(makerspace, domain):
    if domain == "member_cards":
        return module_enabled(makerspace, "membership")
    if domain == "id_programme":
        return programmes_on(makerspace)
    if domain == "event_ticket":
        return module_enabled(makerspace, "events") and feature_enabled(makerspace, EVENT_TICKETS)
    return event_cards_on(makerspace)


def scope_enabled(job):
    space = job.makerspace
    return {"member_cards": lambda: module_enabled(space, "membership"), "id_programme": lambda: programmes_on(space),
            "event": lambda: event_cards_on(space)}[job.scope]()


def wallet_on(kind, makerspace):
    from .wallet.credentials import configured_platforms
    return bool(configured_platforms()) and feature_enabled(makerspace, WALLET[kind])
