"""The staff Shop reports view (#137): totals, channels, payment methods, months, top items."""

from rest_framework import serializers

MONEY = {"max_digits": 14, "decimal_places": 2}


class ShopReportTotalsSerializer(serializers.Serializer):
    orders = serializers.IntegerField()
    sales = serializers.DecimalField(**MONEY)
    refunds = serializers.DecimalField(**MONEY)
    net = serializers.DecimalField(**MONEY)
    tax = serializers.DecimalField(**MONEY)


class ShopReportChannelSerializer(serializers.Serializer):
    channel = serializers.CharField()
    orders = serializers.IntegerField()
    sales = serializers.DecimalField(**MONEY)


class ShopReportMethodSerializer(serializers.Serializer):
    method = serializers.CharField()
    amount = serializers.DecimalField(**MONEY)


class ShopReportMonthSerializer(serializers.Serializer):
    month = serializers.CharField()
    sales = serializers.DecimalField(**MONEY)
    refunds = serializers.DecimalField(**MONEY)


class ShopReportItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    quantity = serializers.IntegerField()
    sales = serializers.DecimalField(**MONEY)


class ShopReportSerializer(serializers.Serializer):
    currency = serializers.CharField()
    totals = ShopReportTotalsSerializer()
    by_channel = ShopReportChannelSerializer(many=True)
    by_method = ShopReportMethodSerializer(many=True)
    by_month = ShopReportMonthSerializer(many=True)
    top_items = ShopReportItemSerializer(many=True)
