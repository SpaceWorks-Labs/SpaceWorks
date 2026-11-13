"""Request/response schemas of the account-level profile (OpenAPI source of truth)."""

from drf_spectacular.utils import extend_schema_serializer
from django.utils.translation import gettext
from rest_framework import serializers

from .models_account_profile import ACTIVITY_TOGGLES, SECTION_TOGGLES, STATUS_KEYS, AccountTimelineEntry
from .profile_serializers import (
    EducationEntrySerializer, ProjectReadSerializer, ProjectWriteSerializer, TagListField,
    MAX_BIO, MAX_EDUCATION, MAX_INTERESTS, MAX_LANGUAGES, MAX_PROJECTS,
)
from .public_profile_validation import HttpsLinkSerializer, SkillSerializer


class AccountProfileWriteSerializer(serializers.Serializer):
    is_visible = serializers.BooleanField(required=False)
    public_visible = serializers.BooleanField(required=False)
    publication_consent = serializers.BooleanField(required=False, write_only=True)
    headline = serializers.CharField(max_length=200, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=[*STATUS_KEYS, ""], required=False)
    status_note = serializers.CharField(max_length=120, required=False, allow_blank=True)
    institution = serializers.CharField(max_length=200, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=MAX_BIO, required=False, allow_blank=True)
    domains = serializers.ListField(child=serializers.CharField(max_length=60), max_length=20, required=False)
    skills = SkillSerializer(many=True, max_length=30, required=False)
    links = HttpsLinkSerializer(many=True, max_length=10, required=False)
    interests = TagListField(max_items=MAX_INTERESTS)
    languages = TagListField(max_items=MAX_LANGUAGES)
    education = serializers.ListField(child=EducationEntrySerializer(), required=False, allow_empty=True,
                                      max_length=MAX_EDUCATION)
    projects = serializers.ListField(child=ProjectWriteSerializer(), required=False, allow_empty=True,
                                     max_length=MAX_PROJECTS)
    # One boolean per section switch, generated from the one tuple so none can be forgotten.
    locals().update({name: serializers.BooleanField(required=False) for name in (*SECTION_TOGGLES, *ACTIVITY_TOGGLES)})
    github_username = serializers.RegexField(
        r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$", required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get("status") == "" and "status_note" not in attrs:
            attrs["status_note"] = ""
        return attrs


class TimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountTimelineEntry
        fields = ("id", "kind", "title", "organization", "location", "start", "end", "description", "order")
        read_only_fields = ("id",)
        extra_kwargs = {"description": {"max_length": 4000}}

    def validate(self, attrs):
        start = attrs.get("start", getattr(self.instance, "start", None))
        end = attrs.get("end", getattr(self.instance, "end", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end": gettext("End must be on or after start.")})
        return attrs


class StatusSerializer(serializers.Serializer):
    preset = serializers.CharField(allow_blank=True)
    note = serializers.CharField(allow_blank=True)


class VerifiedAchievementSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["award", "peoples_choice", "role", "speaker", "attended"])
    event_title = serializers.CharField(allow_blank=True)
    verified_by = serializers.CharField(allow_blank=True)
    occurred_on = serializers.CharField(allow_blank=True)
    rank = serializers.IntegerField(required=False)
    prize_name = serializers.CharField(required=False, allow_blank=True)
    role = serializers.CharField(required=False)
    count = serializers.IntegerField(required=False)


class SelfReportedSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    title = serializers.CharField()
    issuer = serializers.CharField(allow_blank=True)
    achieved_on = serializers.DateField(allow_null=True)
    url = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    order = serializers.IntegerField()


class AchievementsSerializer(serializers.Serializer):
    verified = VerifiedAchievementSerializer(many=True)
    self_reported = SelfReportedSerializer(many=True)


@extend_schema_serializer(component_name="MemberAttendedEvent")
class AttendedEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    space_name = serializers.CharField()


class EventsAttendedSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    recent = AttendedEventSerializer(many=True)


class SpaceRowSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.ChoiceField(choices=["makerspace", "organization"])
    role_title = serializers.CharField(allow_null=True)


class OrganizationRowSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()
    source = serializers.ChoiceField(choices=["explicit", "derived"])


@extend_schema_serializer(component_name="MemberProfileVouch")
class VouchSerializer(serializers.Serializer):
    handle = serializers.CharField()
    display_name = serializers.CharField()
    space_name = serializers.CharField()


class CertificationSerializer(serializers.Serializer):
    name = serializers.CharField()
    space_name = serializers.CharField()


class TimelineRowSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    kind = serializers.CharField()
    title = serializers.CharField()
    organization = serializers.CharField(allow_blank=True)
    location = serializers.CharField(allow_blank=True)
    start = serializers.DateField()
    end = serializers.DateField(allow_null=True)
    description = serializers.CharField(allow_blank=True)
    order = serializers.IntegerField()


@extend_schema_serializer(component_name="MemberAccountProfile")
class AccountProfileSerializer(serializers.Serializer):
    """The profile as one audience reads it. Owner-only keys are absent for other audiences."""

    OWNER_ONLY = ("is_visible", "public_visible", "public_consented_at", "public_reconfirm_pending", "toggles")

    audience = serializers.ChoiceField(choices=["owner", "member", "public"])
    handle = serializers.CharField(allow_null=True)
    account_id = serializers.IntegerField(allow_null=True)
    display_name = serializers.CharField()
    avatar_url = serializers.CharField(allow_null=True)
    headline = serializers.CharField(allow_blank=True)
    institution = serializers.CharField(allow_blank=True)
    shown = serializers.DictField(child=serializers.BooleanField())
    status = StatusSerializer(allow_null=True)
    bio = serializers.CharField(allow_blank=True)
    timeline = TimelineRowSerializer(many=True)
    education = serializers.JSONField()
    skills = SkillSerializer(many=True)
    domains = serializers.ListField(child=serializers.CharField())
    links = serializers.JSONField()
    interests = serializers.ListField(child=serializers.CharField())
    languages = serializers.ListField(child=serializers.CharField())
    projects = ProjectReadSerializer(many=True)
    achievements = AchievementsSerializer()
    events_attended = EventsAttendedSerializer()
    certifications = CertificationSerializer(many=True)
    spaces = SpaceRowSerializer(many=True)
    organizations = OrganizationRowSerializer(many=True)
    vouched_by = VouchSerializer(many=True)
    vouched_count = serializers.IntegerField()
    activity_shown = serializers.DictField(child=serializers.BooleanField())
    github_username = serializers.CharField(allow_blank=True)
    github_contributions = serializers.IntegerField(allow_null=True)
    github_verified = serializers.BooleanField()
    is_visible = serializers.BooleanField(required=False)
    public_visible = serializers.BooleanField(required=False)
    public_consented_at = serializers.DateTimeField(allow_null=True, required=False)
    # Decision 335c: the profile page asks the owner once to confirm open-web publishing again.
    public_reconfirm_pending = serializers.BooleanField(required=False)
    toggles = serializers.DictField(child=serializers.BooleanField(), required=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return {key: value for key, value in data.items()
                if key not in self.OWNER_ONLY or key in instance}
