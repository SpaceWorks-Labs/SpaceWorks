"""L21b member reads and the leader's command for the two hackathon charges.

A team member sees whether the project's entry fee and the team's charge are owed and paid; only the
leader raises the entry fee. Paying uses the ordinary member checkout for the returned payment id (or
the desk). Every route is team-scoped through the submission boundary, so another team reads 404.
"""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models_projects import HackathonSubmission
from .ports import boundary
from .serializers import ErrorSerializer
from .views_base import PrivateSubmissionView

ERRORS = {code: ErrorSerializer for code in (400, 401, 402, 403, 404, 409, 429, 503)}
def charge_read():
    """A fresh field per use: one serializer instance cannot be bound to two fields."""
    return inline_serializer(name="ProgrammeChargeRead", fields={
        "required": serializers.BooleanField(),
        "amount": serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True),
        "payment_id": serializers.IntegerField(allow_null=True),
        "status": serializers.CharField(help_text="not_required, not_raised, or the payment status."),
        "currency": serializers.CharField(allow_blank=True),
    })


FeesRead = inline_serializer(name="ProgrammeChargesRead", fields={"entry_fee": charge_read(), "team_charge": charge_read()})


def _team_charge(event, team):
    from apps.events.hackathons.team_payments import team_fee
    from apps.events.programme_charges import find_charge
    payment = find_charge(event, "team_registration", team.pk)
    amount = team_fee(event)
    return {"required": bool(amount), "amount": amount, "payment_id": payment.pk if payment else None,
            "status": payment.status if payment else ("not_raised" if amount else "not_required"),
            "currency": payment.currency if payment else ""}


def _team(event_id, team_id):
    from apps.events.models import HackathonTeam
    return HackathonTeam.objects.select_related("event__makerspace").get(pk=team_id, event_id=event_id)


class ProgrammeChargesView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: FeesRead, **ERRORS}, tags=["Event submissions"],
                   description="The project's entry fee and the team's leader-paid charge (C-39), for a team member.")
    def get(self, request, pk, team_id, **kwargs):
        from .entry_fees import projection
        with boundary().locked(actor=request.user, event_id=pk, team_id=team_id, action="project_read") as ctx:
            team = _team(pk, team_id)
            project = HackathonSubmission.objects.filter(event_id=pk, team_id=team_id).first()
            return Response({"entry_fee": projection(ctx.event, project), "team_charge": _team_charge(ctx.event, team)})


class EntryFeeView(PrivateSubmissionView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: charge_read(), **ERRORS}, tags=["Event submissions"],
                   description="The leader raises the project's entry fee (idempotent). The project stays a draft "
                               "until it is paid or waived; pay through the member checkout for payment_id.")
    def post(self, request, pk, team_id, **kwargs):
        from .entry_fees import request_entry_fee
        with boundary().locked(actor=request.user, event_id=pk, team_id=team_id, action="save") as ctx:
            return Response(request_entry_fee(actor=request.user, event=ctx.event, team=_team(pk, team_id)))
