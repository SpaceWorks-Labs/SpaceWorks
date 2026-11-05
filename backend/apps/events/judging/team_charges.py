"""Hack-money G15: staff see teams whose team charge was never raised, and raise it now.

The charge is normally raised by a post-commit signal when a team is confirmed; if that signal
fails it only logs. This is the staff work list for those teams and the idempotent retry.
Raising records a debt on the leader (C-39); it never moves money.
"""

from .boundary import command, mutation
from .serializers import CommandInput, validated


def _require(event):
    from .feature import PAID_TEAMS, require_capability
    require_capability(event, PAID_TEAMS)


def missing(event_id, *, actor):
    from .api_common import admin_event_for
    from apps.events.hackathons.team_payments import missing_charges, team_fee
    from .options import currency
    event = admin_event_for(actor, event_id)
    _require(event)
    amount, money = team_fee(event), currency(event.makerspace)
    return [{"team_id": team.pk, "team_name": team.name, "leader_id": team.leader_id, "amount": amount,
             "currency": money} for team in missing_charges(event)]


def projection(team_id, payment):
    return {"team_id": team_id, "payment_id": payment.pk if payment else None,
            "status": payment.status if payment else "not_required",
            "amount": payment.amount if payment else None, "currency": payment.currency if payment else ""}


def raise_now(event_id, team_id, *, actor, data):
    values = validated(CommandInput, data)
    with mutation(event_id, actor) as (event, _):
        _require(event)

        def run():
            from apps.events.hackathons.team_payments import raise_missing
            return projection(team_id, raise_missing(event, team_id, actor))
        return command(event, actor, values, path=f"team-charges/{team_id}/raise", run=run)
