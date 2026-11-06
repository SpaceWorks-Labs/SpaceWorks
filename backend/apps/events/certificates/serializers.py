from django.utils.translation import gettext
from rest_framework import serializers
from apps.events.models_certificates import EventAttendanceCertificate
from apps.events.serializers_staff_tools import StrictSerializer
from apps.events.credentials.views import CredentialCommandSerializer
from .layout import DESIGN_STOCK_CHOICES
from .serializers_layout import CertificateLayerSerializer


class CertificateSubjectSerializer(StrictSerializer):
    subject_kind = serializers.ChoiceField(choices=("registration", "role_assignment"))
    subject_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=EventAttendanceCertificate.Kind.choices)
    award_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)
    result_revision_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)


class BulkIssueSerializer(CredentialCommandSerializer):
    subjects = CertificateSubjectSerializer(many=True, max_length=10000, default=list)
    all_attended = serializers.BooleanField(default=False)
    publish_event_details = serializers.BooleanField(default=True)
    confirmed_count = serializers.IntegerField(min_value=1, max_value=10000)

    def validate(self, data):
        if data["all_attended"] and data["subjects"]:
            raise serializers.ValidationError(gettext("Choose all attended or explicit subjects."))
        if not data["all_attended"] and data["confirmed_count"] != len(data["subjects"]):
            raise serializers.ValidationError({"confirmed_count": gettext("Preview and confirm the selected subject count.")})
        return data


class BatchFailureSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    error_code = serializers.CharField()


class BatchSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    state = serializers.ChoiceField(choices=("queued", "running", "completed", "failed"))
    allowed_actions = serializers.ListField(child=serializers.CharField())
    total = serializers.IntegerField()
    completed = serializers.IntegerField()
    failures = BatchFailureSerializer(many=True)


class PrintCreateSerializer(CredentialCommandSerializer):
    registration_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=200)
    template_revision = serializers.IntegerField(min_value=1)
    stock = serializers.ChoiceField(choices=DESIGN_STOCK_CHOICES)
    include_photo = serializers.BooleanField(default=False)


class PrintAcceptedSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    state = serializers.CharField()
    status_url = serializers.CharField()
    row_failures = serializers.ListField(child=serializers.DictField(), required=False)


class PrintDetailSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    state = serializers.CharField()
    row_failures = serializers.ListField(child=serializers.DictField())
    expires_at = serializers.DateTimeField()


class BadgeDocumentSerializer(StrictSerializer):
    version = serializers.IntegerField(min_value=2, max_value=2)
    page_width_mm = serializers.FloatField(min_value=30, max_value=420)
    page_height_mm = serializers.FloatField(min_value=30, max_value=420)
    layers = CertificateLayerSerializer(many=True, min_length=1, max_length=20)


class BadgeDesignSerializer(CredentialCommandSerializer):
    document = BadgeDocumentSerializer()
    stock = serializers.ChoiceField(choices=DESIGN_STOCK_CHOICES)


class BadgeDesignResultSerializer(StrictSerializer):
    id = serializers.IntegerField()
    document = BadgeDocumentSerializer()
    stock = serializers.ChoiceField(choices=DESIGN_STOCK_CHOICES)
    event_version = serializers.IntegerField(required=False)


class CertificateActionSerializer(CredentialCommandSerializer):
    reason = serializers.ChoiceField(choices=EventAttendanceCertificate.RevocationReason.choices,
                                     required=False, default="staff_revoked")


class CertificateEligibilitySerializer(serializers.Serializer):
    eligible_count = serializers.IntegerField()
    event_version = serializers.IntegerField()
    disclosure = serializers.CharField()


class SeedSerializer(serializers.Serializer):
    seed_id = serializers.CharField()
    seed_version = serializers.IntegerField()
    theme = serializers.ChoiceField(choices=("light", "dark"))
    document = BadgeDocumentSerializer()
    stock = serializers.CharField(allow_null=True)


class SeedPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = SeedSerializer(many=True)
