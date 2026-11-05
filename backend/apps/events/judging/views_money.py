"""Hack-money HTTP adapters (#180). Every write delegates to a workflow that holds the event lock,
the command receipt and the audit; nothing here moves money."""

from rest_framework.response import Response

from . import team_charges
from .api_common import PrivateView, paginated, schema
from .serializers import CommandInput
from .serializers_money import MissingTeamChargeRead, TeamChargeRead


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
