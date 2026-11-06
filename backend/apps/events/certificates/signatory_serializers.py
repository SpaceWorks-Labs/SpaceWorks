from rest_framework import serializers

from apps.accounts.pii_presentation import mask_data, pii_visible
from apps.accounts.platform_authority import is_platform_superadmin
from apps.events.serializers_staff_tools import StrictSerializer


class _Masked(serializers.Serializer):
    """Account names are masked for a superadmin without an open PII window on the space."""
    masked_fields = ()
    pii_masked = serializers.BooleanField(required=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        viewer = getattr(self.context.get("request"), "user", None)
        if is_platform_superadmin(viewer) and not pii_visible(viewer, self.context.get("makerspace_id")):
            if mask_data(data, self.masked_fields):
                data["pii_masked"] = True
        return data


class CertificateSignatoryWriteSerializer(StrictSerializer):
    slot = serializers.IntegerField(min_value=1, max_value=3)
    name = serializers.CharField(max_length=120)
    title = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    member_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None,
                                         help_text="The account that approves designs (required while approval is on).")
    signature_artwork_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None,
                                                    help_text="A finalised upload made with purpose=signature.")


class CertificateSignatoryPolicySerializer(StrictSerializer):
    required = serializers.BooleanField()


class CertificateDesignApprovalSerializer(serializers.Serializer):
    template_revision_id = serializers.IntegerField()
    certificate_kind = serializers.CharField(allow_blank=True)
    slots = serializers.ListField(child=serializers.DictField())
    released = serializers.BooleanField()


class CertificateSignatorySerializer(_Masked):
    masked_fields = ("member_name",)
    id = serializers.IntegerField()
    slot = serializers.IntegerField()
    name = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    member_id = serializers.IntegerField(allow_null=True)
    member_name = serializers.CharField(allow_null=True)
    signature_artwork_id = serializers.IntegerField(allow_null=True)
    version = serializers.IntegerField()


class CertificateSignatoryStateSerializer(serializers.Serializer):
    approval_required = serializers.BooleanField()
    signatories = CertificateSignatorySerializer(many=True)
    designs = CertificateDesignApprovalSerializer(many=True)


class CertificateSignatoryCandidateSerializer(_Masked):
    masked_fields = ("name",)
    id = serializers.IntegerField()
    name = serializers.CharField()


class CertificatePendingApprovalSerializer(serializers.Serializer):
    signatory_id = serializers.IntegerField()
    slot = serializers.IntegerField()
    event_id = serializers.IntegerField()
    event_title = serializers.CharField()
    template_revision_id = serializers.IntegerField()
    certificate_kind = serializers.CharField(allow_blank=True)
    approved = serializers.BooleanField()
    name = serializers.CharField()
    title = serializers.CharField(allow_blank=True)


class CertificateApproveSerializer(StrictSerializer):
    template_revision_id = serializers.IntegerField(min_value=1)


class CertificateApprovalResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    approved_at = serializers.DateTimeField()
