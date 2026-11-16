from rest_framework import serializers

SAFE_ID = 9007199254740991


class KitLineInput(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1, max_value=SAFE_ID)
    quantity_per_person = serializers.IntegerField(min_value=1, max_value=99)
    kind = serializers.ChoiceField(choices=["returnable", "consumable"])


class KitCreateInput(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    lines = KitLineInput(many=True, allow_empty=False, max_length=50)


class KitVersionInput(KitCreateInput):
    expected_revision = serializers.IntegerField(min_value=1, max_value=SAFE_ID)


class KitPublicationInput(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=1, max_value=SAFE_ID)
    published_for_contexts = serializers.BooleanField()


class KitArchiveInput(serializers.Serializer):
    expected_revision = serializers.IntegerField(min_value=1, max_value=SAFE_ID)
    archived = serializers.BooleanField()


class KitSummary(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    revision = serializers.IntegerField()
    current_version = serializers.IntegerField()
    published_for_contexts = serializers.BooleanField()
    archived = serializers.BooleanField()


class KitVersionDetail(serializers.Serializer):
    version = serializers.IntegerField()
    name = serializers.CharField()
    lines = KitLineInput(many=True)


class KitDetail(KitSummary):
    lines = KitLineInput(many=True)


class KitSummaryPage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = KitSummary(many=True)
