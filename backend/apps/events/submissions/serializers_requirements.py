"""Typed bootstrap for the receiving project editor; form JSON belongs to F."""
from rest_framework import serializers


class ProjectBudgetSerializer(serializers.Serializer):
    limit_bytes = serializers.IntegerField(allow_null=True)
    used_bytes = serializers.IntegerField()
    reserved_bytes = serializers.IntegerField()
    remaining_bytes = serializers.IntegerField(allow_null=True)


class ProjectSlotSerializer(serializers.Serializer):
    group = serializers.CharField()
    max_bytes = serializers.IntegerField()


class ProjectTrackSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    version = serializers.IntegerField()
    form = serializers.JSONField()
    criteria = serializers.DictField()


class ProjectPrizeSerializer(ProjectTrackSerializer):
    track_id = serializers.IntegerField(allow_null=True)


class ProjectUploadPolicySerializer(serializers.Serializer):
    name = serializers.CharField()
    version = serializers.IntegerField()


class StageRulesSerializer(serializers.Serializer):
    content_mode = serializers.ChoiceField(choices=("files_and_links", "files_only", "links_only", "presentation"))
    required_link_kinds = serializers.ListField(child=serializers.CharField())
    min_files = serializers.IntegerField()
    max_files = serializers.IntegerField(allow_null=True)
    max_links = serializers.IntegerField(allow_null=True)
    accepted_families = serializers.ListField(child=serializers.CharField())
    max_bytes_per_file = serializers.IntegerField(allow_null=True)
    video_hosts = serializers.ListField(child=serializers.CharField())
    resubmission = serializers.ChoiceField(choices=("until_deadline", "once"))
    late_policy = serializers.ChoiceField(choices=("reject", "accept_flagged"))


class StageFieldSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    type = serializers.ChoiceField(choices=("short_text", "long_text", "choice", "url"))
    required = serializers.BooleanField()
    choices = serializers.ListField(child=serializers.CharField(), allow_null=True, required=False)
    help = serializers.CharField(allow_null=True, allow_blank=True, required=False)


class ParticipantStageSerializer(serializers.Serializer):
    """#178: one submission stage as the team sees it."""
    id = serializers.IntegerField()
    position = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    opens_at = serializers.DateTimeField(allow_null=True)
    deadline = serializers.DateTimeField()
    grace_minutes = serializers.IntegerField()
    effective_deadline = serializers.DateTimeField(help_text="Deadline plus grace, or the team's extension (S2).")
    extended = serializers.BooleanField()
    status = serializers.ChoiceField(choices=("upcoming", "open", "late", "closed"))
    rules = StageRulesSerializer()
    custom_fields = StageFieldSerializer(many=True)
    requires_previous = serializers.BooleanField()
    shortlist_after = serializers.BooleanField()
    shortlist_label = serializers.CharField(allow_blank=True)
    submitted = serializers.BooleanField()
    snapshot_id = serializers.IntegerField(allow_null=True)
    submitted_at = serializers.DateTimeField(allow_null=True)
    blocked = serializers.ChoiceField(choices=("previous_stage_required", "shortlist_pending", "not_shortlisted"),
                                      allow_null=True)
    shortlist_status = serializers.ChoiceField(choices=("pending", "shortlisted", "not_shortlisted"), allow_null=True)
    feedback = serializers.ListField(child=serializers.CharField(), required=False,
                                     help_text="S4: judges' released feedback for this stage, never with a judge's name.")


class ProjectRequirementsSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    deadline = serializers.DateTimeField()
    opens_at = serializers.DateTimeField(allow_null=True)
    grace_seconds = serializers.IntegerField()
    late_policy = serializers.ChoiceField(choices=("reject", "accept_flagged"))
    upload_policy = ProjectUploadPolicySerializer()
    budget = ProjectBudgetSerializer()
    slots = ProjectSlotSerializer(many=True)
    tracks = ProjectTrackSerializer(many=True)
    prizes = ProjectPrizeSerializer(many=True)
    stages = ParticipantStageSerializer(many=True, required=False)
    active_stage_id = serializers.IntegerField(allow_null=True, required=False)
    timezone = serializers.CharField(required=False, help_text="The event's time zone (S13).")
