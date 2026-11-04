"""Concrete admission/bootstrap projections; only F-owned form internals are opaque."""
from rest_framework import serializers


class ContactSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)


class QuoteSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()


class WaiverAcceptanceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.CharField()
    accepted_at = serializers.DateTimeField()


class HostWaiverSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    version = serializers.CharField()
    body = serializers.CharField()
    acceptance_required = serializers.BooleanField()
    accepted_version = serializers.CharField(allow_null=True)
    accepted_at = serializers.DateTimeField(allow_null=True)


class TicketChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    audience = serializers.CharField()
    spots_left = serializers.IntegerField(allow_null=True)


class ContactRequirementSerializer(serializers.Serializer):
    fallback_required = serializers.BooleanField()


class ContactRequirementsSerializer(serializers.Serializer):
    email = ContactRequirementSerializer()
    phone = ContactRequirementSerializer()


class AdmissionRequirementsSerializer(serializers.Serializer):
    registration_audience = serializers.CharField()
    ticket_selection_required = serializers.BooleanField()
    ticket_types = TicketChoiceSerializer(many=True)
    currency = serializers.CharField()
    promo_codes_enabled = serializers.BooleanField()
    invite_code_allowed = serializers.BooleanField()
    verified_email_invite_supported = serializers.BooleanField()
    contact_requirements = ContactRequirementsSerializer()
    host_waiver = HostWaiverSerializer(allow_null=True)


class AnswerReviewSerializer(serializers.Serializer):
    event_date_revision = serializers.IntegerField()
    as_of_date = serializers.DateField()
    locked = serializers.BooleanField()
    date_review_required = serializers.BooleanField()


class SaveIntentSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField()
    state = serializers.CharField()
    status_url = serializers.CharField()


class CocSerializer(serializers.Serializer):
    revision = serializers.IntegerField()
    body = serializers.CharField()


class ContextEventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    public_token = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    timezone_name = serializers.CharField()
    event_date_revision = serializers.IntegerField()
    as_of_date = serializers.DateField()


class ContextMakerspaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.SlugField()


class ContextProgrammeSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["ordinary", "hackathon"])
    capabilities = serializers.DictField(child=serializers.BooleanField())
    team_mode = serializers.CharField(allow_null=True)
    finder_enabled = serializers.BooleanField()


class ContextEligibilitySerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    reason = serializers.CharField(allow_null=True)


class SavedReadinessSerializer(serializers.Serializer):
    readiness = serializers.ChoiceField(choices=["ready", "unavailable"])


class NamedRouteSerializer(serializers.Serializer):
    name = serializers.CharField()
    url = serializers.CharField()


class ContextRoutesSerializer(serializers.Serializer):
    member_base = serializers.CharField()
    context = NamedRouteSerializer()
    application = NamedRouteSerializer(allow_null=True)
    application_submit = NamedRouteSerializer(allow_null=True)
    application_withdraw = NamedRouteSerializer(allow_null=True)
    application_rsvp = NamedRouteSerializer(allow_null=True)
    application_date_review = NamedRouteSerializer(allow_null=True)
    role_postings = NamedRouteSerializer(allow_null=True)
    prefill = NamedRouteSerializer(allow_null=True)
    ordinary_register = NamedRouteSerializer(allow_null=True)


class OptionalConsentSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()
    version = serializers.IntegerField()
    at = serializers.DateTimeField()


class CapacitySerializer(serializers.Serializer):
    offered = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    offer_capacity = serializers.IntegerField(allow_null=True)
    offer_spots_left = serializers.IntegerField(allow_null=True)
    hard_spots_left = serializers.IntegerField(allow_null=True)


class PreviewSkippedSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    people = serializers.IntegerField()
    reason = serializers.CharField()


class PreviewSelectionSerializer(serializers.Serializer):
    selected = serializers.ListField(child=serializers.IntegerField())
    skipped = PreviewSkippedSerializer(many=True)
    offer_spots_left = serializers.IntegerField(allow_null=True)


class PreviewSerializer(serializers.Serializer):
    counts = CapacitySerializer()
    selection = PreviewSelectionSerializer()
