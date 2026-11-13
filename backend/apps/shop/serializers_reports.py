"""The staff Shop reports view (#137): totals, channels, payment methods, months, top items."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

MONEY = {"max_digits": 15, "decimal_places": 3}


class ShopReportTotalsSerializer(serializers.Serializer):
    orders = serializers.IntegerField()
    sales = MoneyField(**MONEY)
    refunds = MoneyField(**MONEY)
    net = MoneyField(**MONEY)
    tax = MoneyField(**MONEY)


class ShopReportChannelSerializer(serializers.Serializer):
    channel = serializers.CharField()
    orders = serializers.IntegerField()
    sales = MoneyField(**MONEY)


class ShopReportMethodSerializer(serializers.Serializer):
    method = serializers.CharField()
    amount = MoneyField(**MONEY)


class ShopReportMonthSerializer(serializers.Serializer):
    month = serializers.CharField()
    sales = MoneyField(**MONEY)
    refunds = MoneyField(**MONEY)


class ShopReportItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    quantity = serializers.IntegerField()
    sales = MoneyField(**MONEY)


class ShopReportSerializer(serializers.Serializer):
    currency = serializers.CharField()
    totals = ShopReportTotalsSerializer()
    by_channel = ShopReportChannelSerializer(many=True)
    by_method = ShopReportMethodSerializer(many=True)
    by_month = ShopReportMonthSerializer(many=True)
    top_items = ShopReportItemSerializer(many=True)
