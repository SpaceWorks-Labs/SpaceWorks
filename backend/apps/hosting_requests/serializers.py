from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.hosting_requests.models import HostingRequest

ACK = {"detail": "Check your email to confirm your request."}
EXPIRING = (HostingRequest.Status.INVITED, HostingRequest.Status.PENDING_VERIFICATION)


class HostingRequestSubmitSerializer(serializers.Serializer):
    applicant_name = serializers.CharField(min_length=2, max_length=200)
    applicant_email = serializers.EmailField(max_length=254)
    applicant_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    space_name = serializers.CharField(min_length=2, max_length=200)
    location = serializers.CharField(min_length=2, max_length=200)
    space_website_url = serializers.URLField(max_length=200, required=False, allow_blank=True, default="")
    description = serializers.CharField(min_length=20, max_length=2000)
    proposed_slug = serializers.SlugField(max_length=50, required=False, allow_blank=True, default="")
    expected_members = serializers.IntegerField(
        min_value=1, max_value=100000, required=False, allow_null=True, default=None,
        help_text="Roughly how many members the space expects (optional).",
    )
    new_organization_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default="",
    )
    website = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
        help_text="Leave empty. Anti-spam field that real browsers never fill.",
    )


class HostingInvitationSubmitSerializer(HostingRequestSubmitSerializer):
    token = serializers.CharField(max_length=200, write_only=True)
    organization_choice = serializers.ChoiceField(
        choices=HostingRequest.OrganizationChoice.choices, default=HostingRequest.OrganizationChoice.OWN,
    )


class HostingTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)


class HostingAckSerializer(serializers.Serializer):
    detail = serializers.CharField()


class HostingRevisionSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("changes_requested", "resubmitted"))
    note = serializers.CharField(allow_blank=True)
    changed_fields = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()


class HostingRequestStatusSerializer(serializers.ModelSerializer):
    rejection_reason = serializers.SerializerMethodField()
    revisions = serializers.SerializerMethodField()
    editable = serializers.SerializerMethodField()

    class Meta:
        model = HostingRequest
        fields = ("status", "space_name", "created_at", "verified_at", "decided_at", "rejection_reason",
                  "changes_note", "revisions", "editable", "location", "space_website_url", "description",
                  "proposed_slug", "new_organization_name")
        read_only_fields = fields

    def get_rejection_reason(self, row) -> str | None:
        return row.rejection_reason if row.status == HostingRequest.Status.REJECTED else None

    @extend_schema_field(HostingRevisionSerializer(many=True))
    def get_revisions(self, row):
        return [{"kind": item.kind, "note": item.note, "changed_fields": item.changed_fields,
                 "created_at": item.created_at} for item in row.revisions.all()[:50]]

    def get_editable(self, row) -> bool:
        from django.conf import settings
        return (row.status == HostingRequest.Status.CHANGES_REQUESTED
                and getattr(settings, "HOSTING_REQUEST_RESUBMIT_ENABLED", True))

    EDIT_FIELDS = ("location", "space_website_url", "description", "proposed_slug", "new_organization_name")

    def to_representation(self, row):
        # The editable details travel back only while the applicant is asked to change them.
        data = super().to_representation(row)
        if not data["editable"]:
            for name in self.EDIT_FIELDS:
                data.pop(name, None)
        return data


class HostingResubmitSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200, write_only=True)
    space_name = serializers.CharField(min_length=2, max_length=200, required=False)
    location = serializers.CharField(min_length=2, max_length=200, required=False)
    space_website_url = serializers.URLField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(min_length=20, max_length=2000, required=False)
    proposed_slug = serializers.SlugField(max_length=50, required=False, allow_blank=True)
    new_organization_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class HostingInvitationPreviewSerializer(serializers.Serializer):
    inviter_name = serializers.CharField()
    join_organization_name = serializers.CharField(allow_null=True)
    space_name = serializers.CharField(allow_blank=True)
    applicant_email = serializers.EmailField(allow_blank=True)
    invite_note = serializers.CharField(allow_blank=True)
    expires_at = serializers.DateTimeField()


class HostingInvitationCreateSerializer(serializers.Serializer):
    invitee_email = serializers.EmailField(max_length=254)
    space_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class HostingInvitationSerializer(serializers.ModelSerializer):
    """What an inviter may see: never the applicant's address, name, phone or reason."""

    display_status = serializers.SerializerMethodField()
    join_offered = serializers.SerializerMethodField()

    class Meta:
        model = HostingRequest
        fields = (
            "id", "space_name", "status", "display_status", "join_offered", "created_at",
            "invite_expires_at",
        )
        read_only_fields = fields

    def get_display_status(self, row) -> str:
        from django.utils import timezone

        if row.status in EXPIRING and row.invite_expires_at and row.invite_expires_at <= timezone.now():
            return "expired"
        return row.status

    def get_join_offered(self, row) -> bool:
        return row.inviter_organization_id is not None


class HostingInvitationCreatedSerializer(HostingInvitationSerializer):
    invite_url = serializers.CharField()
    delivery_status = serializers.CharField()

    class Meta(HostingInvitationSerializer.Meta):
        fields = (*HostingInvitationSerializer.Meta.fields, "invite_url", "delivery_status")
        read_only_fields = fields


class HostingInvitationPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = HostingInvitationSerializer(many=True)
