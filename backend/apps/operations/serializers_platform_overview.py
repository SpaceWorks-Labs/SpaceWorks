"""OpenAPI shapes of the superadmin platform overview (#183A). Counts and money only."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.operations.platform_overview_window import PRESETS

UNITS = ("count", "hours", "bytes", "percent", "money")
TIMINGS = ("period", "snapshot")


class OverviewWindowSerializer(serializers.Serializer):
    preset = serializers.ChoiceField(choices=PRESETS)
    starts_at = serializers.DateTimeField(allow_null=True, help_text="Null for all time.")
    ends_at = serializers.DateTimeField()


class OverviewMetricSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    unit = serializers.ChoiceField(choices=UNITS)
    timing = serializers.ChoiceField(choices=TIMINGS, help_text="snapshot = the state now; period = inside the window.")


class OverviewPlatformMetricSerializer(OverviewMetricSerializer):
    value = serializers.IntegerField(min_value=0)


class OverviewBlockRowSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    values = serializers.DictField(child=serializers.FloatField(allow_null=True), allow_null=True,
                                   help_text="Null when the block's module is off in this space.")


class OverviewBlockSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    switches = serializers.ListField(child=serializers.CharField(), help_text="Module or capability keys that gate it.")
    on_in = serializers.IntegerField(min_value=0)
    off_in = serializers.IntegerField(min_value=0)
    metrics = OverviewMetricSerializer(many=True)
    totals = serializers.DictField(child=serializers.FloatField(allow_null=True),
                                   help_text="Sum of the per-space rows; percent metrics are recomputed from sums.")
    rows = OverviewBlockRowSerializer(many=True)
    platform_metrics = OverviewPlatformMetricSerializer(many=True, help_text="Deployment-wide numbers with no space.")


class OverviewHiddenBlockSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    switches = serializers.ListField(child=serializers.CharField())
    on_in = serializers.IntegerField(min_value=0)
    off_in = serializers.IntegerField(min_value=0)


class OverviewMoneyFiguresSerializer(serializers.Serializer):
    charges = serializers.IntegerField(min_value=0)
    amounts = serializers.DictField(child=MoneyField(max_digits=17, decimal_places=3, coerce_to_string=True))


class OverviewMoneyRowSerializer(OverviewMoneyFiguresSerializer):
    makerspace_id = serializers.IntegerField()


class OverviewCurrencySerializer(serializers.Serializer):
    currency = serializers.CharField(max_length=3)
    totals = OverviewMoneyFiguresSerializer()
    rows = OverviewMoneyRowSerializer(many=True)


class OverviewMoneySerializer(OverviewHiddenBlockSerializer):
    metrics = OverviewMetricSerializer(many=True)
    currencies = OverviewCurrencySerializer(many=True, help_text="One entry per currency; never summed across.")


class OverviewSpaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    excluded_reason = serializers.CharField(
        allow_null=True, help_text="archived, importing, aborted or directory_hidden; null when counted by default.")
    directory_hidden = serializers.BooleanField()


class OverviewModuleSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    on_in = serializers.IntegerField(min_value=0)
    off_in = serializers.IntegerField(min_value=0)
    space_ids = serializers.ListField(child=serializers.IntegerField())


class PlatformOverviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("ready",))
    computed_at = serializers.DateTimeField()
    window = OverviewWindowSerializer()
    include_excluded = serializers.BooleanField()
    excluded_count = serializers.IntegerField(min_value=0)
    spaces = OverviewSpaceSerializer(many=True)
    reports_space_ids = serializers.ListField(
        child=serializers.IntegerField(), help_text="Space IDs where Reports is currently available.",
    )
    blocks = OverviewBlockSerializer(many=True)
    money = OverviewMoneySerializer(allow_null=True)
    hidden_blocks = OverviewHiddenBlockSerializer(many=True, help_text="Blocks whose module is off in every space.")
    modules = OverviewModuleSerializer(many=True)


class PlatformOverviewComputingSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=("computing",))
    retry_after_seconds = serializers.IntegerField(min_value=1)


class PlatformOverviewErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField(required=False)
