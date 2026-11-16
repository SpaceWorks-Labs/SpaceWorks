from django.utils.translation import gettext
from rest_framework import serializers


class ProblemReportTriageResolutionSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class ProblemReportTriageSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=["no_issue", "damaged", "missing", "needs_fix"]
    )
    resolutions = ProblemReportTriageResolutionSerializer(
        many=True, required=False, default=list
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")
    evidence_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        resolutions = attrs.get("resolutions", [])
        item_ids = [entry["item_id"] for entry in resolutions]
        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                {"resolutions": gettext("Duplicate item_id values are not allowed.")}
            )
        if attrs["outcome"] != "no_issue" and not resolutions:
            raise serializers.ValidationError(
                {"resolutions": gettext("At least one item must be triaged.")}
            )
        return attrs


class ProblemReportTriageResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    outcome = serializers.CharField()
    resolved = serializers.BooleanField()

class ProblemReportResolvedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    resolved = serializers.BooleanField()


class AccountabilityTruncationSerializer(serializers.Serializer):
    repeat_offenders = serializers.BooleanField()
    overdue = serializers.BooleanField()
    problem_reports = serializers.BooleanField()


class AccountabilityReportSerializer(serializers.Serializer):
    """The accountability dashboard (#193 OpenAPI contract); each list holds report rows."""
    repeat_offenders = serializers.ListField(child=serializers.DictField())
    anonymous_accountability = serializers.DictField()
    overdue = serializers.ListField(child=serializers.DictField())
    restrictions = serializers.ListField(child=serializers.DictField())
    problem_reports = serializers.ListField(child=serializers.DictField())
    truncated = AccountabilityTruncationSerializer()


class ProblemReportQueueSerializer(serializers.Serializer):
    """Open problem reports for the inventory area (decision 224(a): not the people page)."""
    results = serializers.ListField(child=serializers.DictField())
    truncated = serializers.BooleanField()
