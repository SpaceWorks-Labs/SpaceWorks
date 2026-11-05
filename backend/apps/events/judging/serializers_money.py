"""Hack-money closed inputs and reads (team-charge retry, prize money, deposits)."""

from rest_framework import serializers

from .serializers import ClosedSerializer

MONEY = dict(max_digits=12, decimal_places=2)


class MissingTeamChargeRead(ClosedSerializer):
    team_id = serializers.IntegerField()
    team_name = serializers.CharField()
    leader_id = serializers.IntegerField()
    amount = serializers.DecimalField(**MONEY, allow_null=True)
    currency = serializers.CharField()


class TeamChargeRead(ClosedSerializer):
    team_id = serializers.IntegerField()
    payment_id = serializers.IntegerField(allow_null=True)
    status = serializers.CharField()
    amount = serializers.DecimalField(**MONEY, allow_null=True)
    currency = serializers.CharField(allow_blank=True)
