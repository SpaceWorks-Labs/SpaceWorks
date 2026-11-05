"""Hack-money HTTP adapters (#180). Every write delegates to a workflow that holds the event lock,
the command receipt and the audit; nothing here moves money."""

from rest_framework.response import Response

from . import deposits, team_charges
from .api_common import PrivateView, paginated, schema
from .serializers import CommandInput
from .serializers_money import DepositSettlementRead, MissingTeamChargeRead, TeamChargeRead


class MissingTeamCharges(PrivateView):
    @schema(response=MissingTeamChargeRead(many=True), page=True,
            description="Confirmed teams whose team charge was never raised (a failed signal). events.paid_teams.")
    def get(self, request, pk):
        return paginated(request, team_charges.missing(pk, actor=request.user), MissingTeamChargeRead)


class TeamChargeRaise(PrivateView):
    @schema(request=CommandInput, response=TeamChargeRead,
            description="Raise the team's missing charge on its leader now (idempotent; expected_version 0). "
                        "404 when the team owes no charge.")
    def post(self, request, pk, team_id):
        return Response(team_charges.raise_now(pk, team_id, actor=request.user, data=request.data))


class DepositSettlement(PrivateView):
    @schema(response=DepositSettlementRead,
            description="G10: what settling this event's deposits would do, per deposit. events.deposits; "
                        "record_payment or the Event Manager.")
    def get(self, request, pk):
        from .prize_access import event_for_money
        event = event_for_money(request.user, pk)
        return Response(DepositSettlementRead(deposits.summary(event, actor=request.user)).data)


class DepositSettle(PrivateView):
    @schema(request=CommandInput, response=DepositSettlementRead,
            description="G10: staff approve the settlement batch once, after the event (expected_version = the "
                        "options version). Attendees get refund DUE cases staff still approve; no-shows keep the "
                        "charge. 409 already_settled / event_not_ended.")
    def post(self, request, pk):
        return Response(deposits.settle(pk, actor=request.user, data=request.data))
