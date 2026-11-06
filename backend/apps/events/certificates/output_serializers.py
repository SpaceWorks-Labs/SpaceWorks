from rest_framework import serializers

from apps.events.serializers_staff_tools import StrictSerializer
from .signatory_serializers import _Masked

KINDS = ("attendance", "participant", "finalist", "winner", "volunteer_thanks", "mentor_thanks",
         "judge_thanks", "organiser_thanks")


class HolderCertificateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    event_title = serializers.CharField()
    event_date = serializers.DateTimeField()
    issuer_name = serializers.CharField()
    kind = serializers.ChoiceField(choices=KINDS)
    kind_title = serializers.CharField()
    award = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=("pending", "rendering", "active", "failed", "revoked"))
    issued_at = serializers.DateTimeField()
    revision = serializers.IntegerField()
    serial = serializers.UUIDField()
    verifiable = serializers.BooleanField(help_text="Public verification is on; sharing and LinkedIn links work.")
    verify_url = serializers.URLField(allow_null=True)
    holder_name_public = serializers.BooleanField()


class CertificateHolderNameSerializer(StrictSerializer):
    show = serializers.BooleanField(help_text="Show your name on the public verification page and share image.")


class IssuedCertificateSerializer(_Masked):
    masked_fields = ("recipient_name",)
    id = serializers.IntegerField()
    recipient_name = serializers.CharField()
    kind = serializers.ChoiceField(choices=KINDS)
    kind_title = serializers.CharField()
    award = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    revision = serializers.IntegerField()
    issued_at = serializers.DateTimeField()
    public_verification_enabled = serializers.BooleanField()
    revocation_reason = serializers.CharField(allow_blank=True)


class IssuedCertificatePageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = IssuedCertificateSerializer(many=True)


class CertificateIssuePlanRequestSerializer(StrictSerializer):
    groups = serializers.ListField(child=serializers.ChoiceField(choices=("attendance", "participants", "awards", "roles")),
                                   min_length=1, max_length=4)


class CertificatePlannedSubjectSerializer(StrictSerializer):
    subject_kind = serializers.ChoiceField(choices=("registration", "role_assignment"))
    subject_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=KINDS)
    award_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)
    result_revision_id = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)


class CertificatePlannedRowSerializer(_Masked):
    masked_fields = ("name",)
    subject_kind = serializers.CharField()
    subject_id = serializers.IntegerField()
    kind = serializers.CharField()
    award_id = serializers.IntegerField(allow_null=True)
    result_revision_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    kind_title = serializers.CharField()
    award = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False)


class CertificateIssuePlanSerializer(serializers.Serializer):
    event_version = serializers.IntegerField()
    recipients = CertificatePlannedRowSerializer(many=True)
    skipped = CertificatePlannedRowSerializer(many=True)
    counts = serializers.DictField(child=serializers.IntegerField())


class VerificationSerializer(serializers.Serializer):
    event = serializers.CharField()
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=("valid", "revoked"))
    issuer = serializers.CharField()
    kind = serializers.ChoiceField(choices=KINDS)
    kind_title = serializers.CharField()
    award = serializers.CharField(allow_blank=True)
    recipient_name = serializers.CharField(allow_null=True, help_text="Only when the holder chose to show it.")
    status_note = serializers.CharField()
    serial = serializers.UUIDField()
    sha256 = serializers.CharField(help_text="SHA-256 of the issued PDF bytes; compare a file you were given.")
