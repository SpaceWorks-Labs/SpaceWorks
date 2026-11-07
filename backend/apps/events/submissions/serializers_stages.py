"""Closed schemas for the submission-stage routes (#177-#180)."""
from django.utils.translation import gettext
from rest_framework import serializers

from .links import KINDS
from .models_stages import CONTENT_MODES, LATE_POLICIES, MAX_STAGES, RESUBMISSION
from .serializers import ClosedSerializer
from .stage_rules import FAMILIES, FIELD_TYPES, FIELD_VISIBILITY, VIDEO_HOSTS

TRIAGE = ("pending", "eligible", "ineligible", "hidden")


class StageCustomFieldInput(ClosedSerializer):
    key = serializers.RegexField(r"^[a-z][a-z0-9_]{0,39}$")
    label = serializers.CharField(max_length=120)
    type = serializers.ChoiceField(choices=FIELD_TYPES)
    required = serializers.BooleanField(default=False)
    choices = serializers.ListField(child=serializers.CharField(max_length=80), max_length=20, required=False, default=list)
    help = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    visible_to = serializers.ChoiceField(choices=FIELD_VISIBILITY, default="staff_and_judges",
                                         help_text="S7: who may read the answer. Public choice fields filter the gallery.")

    def validate(self, data):
        if data["type"] == "choice" and (len(data["choices"]) < 2 or len(set(data["choices"])) != len(data["choices"])):
            raise serializers.ValidationError({"choices": gettext("A choice field needs at least two distinct choices.")})
        if data["type"] != "choice":
            data["choices"] = []
        return data


class SubmissionStageInput(ClosedSerializer):
    id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=2000, allow_blank=True, required=False, default="")
    opens_at = serializers.DateTimeField(allow_null=True, required=False, default=None)
    deadline = serializers.DateTimeField(allow_null=True, required=False, default=None)
    grace_minutes = serializers.IntegerField(min_value=0, max_value=1440, required=False, default=0)
    late_policy = serializers.ChoiceField(choices=LATE_POLICIES, required=False, default="reject")
    resubmission = serializers.ChoiceField(choices=RESUBMISSION, required=False, default="until_deadline")
    requires_previous = serializers.BooleanField(required=False, default=False)
    content_mode = serializers.ChoiceField(choices=CONTENT_MODES, required=False, default="files_and_links")
    # A plain string list (checked below), so the shared LinkKindEnum keeps its OpenAPI name.
    required_link_kinds = serializers.ListField(child=serializers.CharField(max_length=16), max_length=8,
                                                required=False, default=list, help_text="Link kinds: " + ", ".join(sorted(KINDS)))
    min_files = serializers.IntegerField(min_value=0, max_value=100, required=False, default=0)
    max_files = serializers.IntegerField(min_value=1, max_value=100, allow_null=True, required=False, default=None)
    max_links = serializers.IntegerField(min_value=1, max_value=30, allow_null=True, required=False, default=None)
    accepted_families = serializers.ListField(child=serializers.ChoiceField(choices=FAMILIES), max_length=len(FAMILIES),
                                              required=False, default=list)
    max_bytes_per_file = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)
    video_hosts = serializers.ListField(child=serializers.ChoiceField(choices=VIDEO_HOSTS), max_length=len(VIDEO_HOSTS),
                                        required=False, default=list)
    custom_fields = StageCustomFieldInput(many=True, required=False, default=list, max_length=20)
    shortlist_after = serializers.BooleanField(required=False, default=False)
    shortlist_label = serializers.CharField(max_length=60, allow_blank=True, required=False, default="")
    public_after_publish = serializers.BooleanField(required=False, default=False,
                                                    help_text="S18: this stage's work may join the gallery once published.")

    def validate(self, data):
        if not set(data["required_link_kinds"]) <= KINDS:
            raise serializers.ValidationError({"required_link_kinds": gettext("Use known link kinds.")})
        for key in ("required_link_kinds", "accepted_families", "video_hosts"):
            data[key] = sorted(set(data[key]))
        return data


class StagePlanInput(ClosedSerializer):
    operation_id = serializers.UUIDField()
    expected_fingerprint = serializers.CharField(max_length=64)
    preset = serializers.CharField(max_length=40, allow_blank=True, required=False, default="")
    stages = SubmissionStageInput(many=True, min_length=1, max_length=MAX_STAGES)


class StaffStageSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    position = serializers.IntegerField()
    version = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    opens_at = serializers.DateTimeField(allow_null=True)
    deadline = serializers.DateTimeField(allow_null=True)
    grace_minutes = serializers.IntegerField()
    late_policy = serializers.CharField()
    resubmission = serializers.CharField()
    requires_previous = serializers.BooleanField()
    content_mode = serializers.CharField()
    required_link_kinds = serializers.ListField(child=serializers.CharField())
    min_files = serializers.IntegerField()
    max_files = serializers.IntegerField(allow_null=True)
    max_links = serializers.IntegerField(allow_null=True)
    accepted_families = serializers.ListField(child=serializers.CharField())
    max_bytes_per_file = serializers.IntegerField(allow_null=True)
    video_hosts = serializers.ListField(child=serializers.CharField())
    custom_fields = serializers.ListField(child=serializers.DictField())
    shortlist_after = serializers.BooleanField()
    shortlist_label = serializers.CharField(allow_blank=True)
    public_after_publish = serializers.BooleanField(required=False)
    submissions = serializers.IntegerField(required=False)
    pending_triage = serializers.IntegerField(required=False)
    shortlist = serializers.DictField(required=False)
    extensions = serializers.ListField(child=serializers.DictField(), required=False)
    warnings = serializers.ListField(child=serializers.CharField(), required=False,
                                     help_text="S13: ambiguous_deadline_time when a deadline is 00:00 or 12:00 event time.")


class StagePlanSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    fingerprint = serializers.CharField()
    stages = StaffStageSerializer(many=True)
    timezone = serializers.CharField()
    event_ends_at = serializers.DateTimeField()
    presets = serializers.ListField(child=serializers.DictField())
    families = serializers.ListField(child=serializers.CharField())
    link_kinds = serializers.ListField(child=serializers.CharField())
    video_hosts = serializers.ListField(child=serializers.CharField())
    field_types = serializers.ListField(child=serializers.CharField())
    field_visibility = serializers.ListField(child=serializers.CharField())
    max_stages = serializers.IntegerField()
    answer_limits = serializers.DictField(child=serializers.IntegerField())
    admission_enabled = serializers.BooleanField()


class ShortlistPreviewInput(ClosedSerializer):
    selection = serializers.ChoiceField(choices=("top_n", "manual"))
    top_n = serializers.IntegerField(min_value=1, max_value=1000, required=False)
    source_round_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    submission_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=2000, required=False,
                                           default=list)

    def validate(self, data):
        if data["selection"] == "top_n" and (not data.get("top_n") or not data.get("source_round_id")):
            raise serializers.ValidationError({"top_n": gettext("Top N needs a number and a finalized round on this stage.")})
        return data


class ShortlistApplyInput(ShortlistPreviewInput):
    operation_id = serializers.UUIDField()
    fingerprint = serializers.CharField(max_length=64)


class ShortlistPublishInput(ClosedSerializer):
    operation_id = serializers.UUIDField()
    shortlist_id = serializers.IntegerField(min_value=1)


class ShortlistPromoteInput(ClosedSerializer):
    operation_id = serializers.UUIDField()
    withdrawn_submission_id = serializers.IntegerField(min_value=1)


class ShortlistEntrySerializer(serializers.Serializer):
    submission_id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    snapshot_id = serializers.IntegerField()
    title = serializers.CharField(allow_blank=True)
    source_rank = serializers.IntegerField(allow_null=True)


class ShortlistPlanSerializer(serializers.Serializer):
    stage_id = serializers.IntegerField()
    source_round_id = serializers.IntegerField(allow_null=True)
    selection = serializers.CharField()
    top_n = serializers.IntegerField(allow_null=True)
    tied_at_cutoff = serializers.BooleanField()
    fingerprint = serializers.CharField()
    entries = ShortlistEntrySerializer(many=True)
    candidates = serializers.IntegerField()
    not_shortlisted = serializers.IntegerField()
    email_enabled = serializers.BooleanField(help_text="S11: when false, teams are NOT emailed on publish.")


class ShortlistCurrentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    selection = serializers.CharField()
    top_n = serializers.IntegerField(allow_null=True)
    source_round_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    published_at = serializers.DateTimeField(allow_null=True)
    entries = ShortlistEntrySerializer(many=True)


class StageEntryRowSerializer(serializers.Serializer):
    submission_id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    team_name = serializers.CharField()
    snapshot_id = serializers.IntegerField()
    triage = serializers.CharField()
    submitted_at = serializers.DateTimeField(allow_null=True)


class ShortlistSerializer(serializers.Serializer):
    stage_id = serializers.IntegerField()
    label = serializers.CharField(allow_blank=True)
    pending_triage = serializers.IntegerField()
    stage_entries = StageEntryRowSerializer(many=True, help_text="Live submissions of the stage, for picks and triage.")
    candidates = serializers.IntegerField()
    email_enabled = serializers.BooleanField()
    current = ShortlistCurrentSerializer(allow_null=True)
    allowed_actions = serializers.ListField(child=serializers.CharField())


class ExtensionInput(ClosedSerializer):
    operation_id = serializers.UUIDField()
    team_id = serializers.IntegerField(min_value=1)
    until = serializers.DateTimeField()
    reason = serializers.CharField(max_length=1000)


class ExtensionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    stage_id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    team_name = serializers.CharField()
    until = serializers.DateTimeField()
    reason = serializers.CharField()
    created_at = serializers.DateTimeField()


class BulkTriageInput(ClosedSerializer):
    operation_id = serializers.UUIDField()
    submission_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=500)
    triage = serializers.ChoiceField(choices=TRIAGE)
    reason = serializers.CharField(max_length=1000)


class BulkTriageSerializer(serializers.Serializer):
    stage_id = serializers.IntegerField()
    updated = serializers.IntegerField()
    triage = serializers.CharField()
