"""Lane schemas; F supplies the internals of versioned form descriptors."""
from rest_framework import serializers
from drf_spectacular.utils import inline_serializer
from .api_schema_staff import ReviewApplicationSerializer
from .api_schema_teams import RosterMemberSerializer, JoinRequestSerializer
from .api_schema_details import (
    AdmissionRequirementsSerializer, AnswerReviewSerializer, CocSerializer, ContactSerializer,
    ContextEligibilitySerializer, ContextEventSerializer, ContextMakerspaceSerializer,
    ContextProgrammeSerializer, ContextRoutesSerializer, OptionalConsentSerializer,
    QuoteSerializer, SavedReadinessSerializer, SaveIntentSerializer, WaiverAcceptanceSerializer,
)


class ProgrammeErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
    fields = serializers.DictField()
    current_version = serializers.IntegerField(required=False)


ERRORS = {code: ProgrammeErrorSerializer for code in (400, 401, 403, 404, 409, 410, 413, 423, 429, 503)}


class AggregateSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class AdmissionProjectionSerializer(serializers.Serializer):
    ticket_type_id = serializers.IntegerField(allow_null=True)
    contact = ContactSerializer()
    quote = QuoteSerializer(allow_null=True)
    invite_applied = serializers.BooleanField()
    promo_applied = serializers.BooleanField()
    host_waiver_acceptance = WaiverAcceptanceSerializer(allow_null=True)


class ApplicationSerializer(AggregateSerializer):
    registration_id = serializers.IntegerField(allow_null=True)
    form = serializers.JSONField()
    answers = serializers.ListField(child=serializers.DictField())
    answer_review = AnswerReviewSerializer(required=False)
    omitted_question_ids = serializers.ListField(child=serializers.CharField(), required=False)
    admission_requirements = AdmissionRequirementsSerializer()
    admission = AdmissionProjectionSerializer()
    save_intent = SaveIntentSerializer(allow_null=True)
    rsvp_due_at = serializers.DateTimeField(allow_null=True, required=False)
    rsvp_accepted_at = serializers.DateTimeField(allow_null=True, required=False)
    coc = CocSerializer(allow_null=True, required=False)
    optional_consent_purposes = serializers.ListField(child=serializers.CharField(), required=False)
    optional_consents = serializers.DictField(child=OptionalConsentSerializer(), required=False)


class ContextSerializer(serializers.Serializer):
    context_version = serializers.IntegerField()
    event = ContextEventSerializer()
    makerspace = ContextMakerspaceSerializer()
    programme = ContextProgrammeSerializer()
    application_form = serializers.JSONField(allow_null=True)
    registration_form = serializers.JSONField(allow_null=True)
    coc = CocSerializer(allow_null=True)
    admission_requirements = serializers.DictField()
    eligibility = ContextEligibilitySerializer()
    saved_details = SavedReadinessSerializer()
    routes = ContextRoutesSerializer()


class TeamSerializer(AggregateSerializer):
    name = serializers.CharField()
    leader_member_id = serializers.IntegerField()
    team_mode = serializers.CharField()
    seeking_members = serializers.BooleanField()
    finder_intro = serializers.CharField()
    skills = serializers.ListField(child=serializers.CharField())
    eligibility_issue = serializers.BooleanField()
    roster_hash = serializers.CharField()
    members = RosterMemberSerializer(many=True)
    join_requests = JoinRequestSerializer(many=True)


class CommentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    body = serializers.CharField(max_length=2000)
    created_at = serializers.DateTimeField()
    team_version = serializers.IntegerField()


class InviteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    team_version = serializers.IntegerField()
    token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class ReviewSerializer(AggregateSerializer):
    round = serializers.IntegerField()
    rubric = serializers.DictField()
    applications = ReviewApplicationSerializer(many=True)
    completed_scores = serializers.ListField(child=serializers.DictField(), required=False)


class BatchSerializer(AggregateSerializer):
    decisions = serializers.ListField(child=serializers.DictField())


class FinderSerializer(AggregateSerializer):
    opted_in = serializers.BooleanField()
    intro = serializers.CharField()
    skills = serializers.ListField(child=serializers.CharField())


def page_schema(item):
    return {"type": "object", "required": ["count", "next", "previous", "results"],
            "properties": {"count": {"type": "integer"}, "next": {"type": "string", "nullable": True},
                           "previous": {"type": "string", "nullable": True}, "results": {"type": "array", "items": item}}}


def paginated_schema(name, item):
    return inline_serializer(name=name, fields={
        "count": serializers.IntegerField(), "next": serializers.CharField(allow_null=True),
        "previous": serializers.CharField(allow_null=True), "results": item(many=True)})
