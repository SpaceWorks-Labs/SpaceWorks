"""Bounded configuration, excluding publication/retention pointers."""
from django.utils.translation import gettext
from rest_framework import serializers
from .admission_inputs import CommandInput, LiteralBoolean


class ConfigInput(CommandInput):
    enabled = LiteralBoolean(required=False)
    review_mode = serializers.ChoiceField(choices=["auto", "rolling", "batch"], required=False)
    application_opens_at = serializers.DateTimeField(allow_null=True, required=False)
    application_closes_at = serializers.DateTimeField(allow_null=True, required=False)
    application_form = serializers.JSONField(required=False)
    team_mode = serializers.ChoiceField(choices=["solo", "individual_then_team", "team_together"], required=False)
    finder_enabled = LiteralBoolean(required=False)
    team_min = serializers.IntegerField(min_value=1, max_value=100, required=False)
    team_max = serializers.IntegerField(min_value=1, max_value=100, required=False)
    team_lock_at = serializers.DateTimeField(allow_null=True, required=False)
    team_eligibility = serializers.ChoiceField(choices=["offered", "confirmed"], required=False)
    review_count = serializers.IntegerField(min_value=1, max_value=20, required=False)
    blind_review = LiteralBoolean(required=False)
    review_rubric = serializers.DictField(required=False)
    review_round_closed = LiteralBoolean(required=False)
    rsvp_days = serializers.IntegerField(min_value=1, max_value=30, required=False)
    offer_capacity = serializers.IntegerField(min_value=0, allow_null=True, required=False)
    submission_opens_at = serializers.DateTimeField(allow_null=True, required=False)
    submission_deadline = serializers.DateTimeField(allow_null=True, required=False)
    submission_grace_minutes = serializers.IntegerField(min_value=0, max_value=1440, required=False)
    late_policy = serializers.ChoiceField(choices=["reject", "accept_flagged"], required=False)
    attendance_required = LiteralBoolean(required=False)
    upload_policy = serializers.CharField(max_length=64, required=False)
    upload_policy_version = serializers.IntegerField(min_value=1, required=False)
    storage_budget_bytes = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    coc_body = serializers.CharField(max_length=50000, required=False)
    optional_mlh_schema = serializers.DictField(required=False)


def validate_rubric(rubric):
    if set(rubric) != {"revision", "criteria"} or type(rubric["revision"]) is not int or rubric["revision"] < 1:
        raise serializers.ValidationError({"review_rubric": gettext("Use revision and anchored criteria.")})
    criteria = rubric["criteria"]
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 20:
        raise serializers.ValidationError({"review_rubric": gettext("Use 1–20 criteria.")})
    seen = set()
    for item in criteria:
        if not isinstance(item, dict) or set(item) != {"key", "label", "anchors"}:
            raise serializers.ValidationError({"review_rubric": gettext("Use key, label and anchors.")})
        if not isinstance(item["key"], str) or not item["key"].isidentifier() or len(item["key"]) > 40 or item["key"] in seen:
            raise serializers.ValidationError({"review_rubric": gettext("Use distinct short criterion keys.")})
        if not isinstance(item["label"], str) or not 1 <= len(item["label"].strip()) <= 200:
            raise serializers.ValidationError({"review_rubric": gettext("Use bounded criterion labels.")})
        if not isinstance(item["anchors"], dict) or set(item["anchors"]) != set("12345") or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 500 for v in item["anchors"].values()):
            raise serializers.ValidationError({"review_rubric": gettext("Describe every score from 1 to 5.")})
        seen.add(item["key"])
    return rubric
