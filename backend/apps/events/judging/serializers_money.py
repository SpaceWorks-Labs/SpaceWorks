"""Hack-money closed inputs and reads (team-charge retry, prize money, deposits)."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from .serializers import ClosedSerializer

from apps.payments.money import MONEY  # noqa: E402


class MissingTeamChargeRead(ClosedSerializer):
    team_id = serializers.IntegerField()
    team_name = serializers.CharField()
    leader_id = serializers.IntegerField()
    amount = MoneyField(**MONEY, allow_null=True)
    currency = serializers.CharField()


class DepositRow(ClosedSerializer):
    payment_id = serializers.IntegerField()
    registration_id = serializers.IntegerField()
    member_id = serializers.IntegerField(allow_null=True)
    amount = MoneyField(**MONEY)
    currency = serializers.CharField()
    payment_status = serializers.CharField()
    outcome = serializers.ChoiceField(choices=("return", "void", "keep", "none"),
                                      help_text="return: a refund DUE case staff approve; void: pending, not owed; "
                                                "keep: a no-show keeps the charge; none: already decided.")


class DepositSettlementRead(ClosedSerializer):
    event_id = serializers.IntegerField()
    amount = MoneyField(**MONEY, allow_null=True)
    requires_submission = serializers.BooleanField()
    settled_at = serializers.DateTimeField(allow_null=True)
    event_ended = serializers.BooleanField()
    rows = DepositRow(many=True)


class TeamChargeRead(ClosedSerializer):
    team_id = serializers.IntegerField()
    payment_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    amount = MoneyField(**MONEY, allow_null=True)
    currency = serializers.CharField(allow_blank=True)
