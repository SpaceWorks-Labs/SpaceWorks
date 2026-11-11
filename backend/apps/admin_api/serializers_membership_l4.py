"""Staff-console shapes for the L4 membership lifecycle.

Every serializer that returns registry PII (GSTIN, notes, imported contact details) or an
account's email/name adopts `PiiMaskingSerializerMixin`, so a superadmin without an open
PII window on the space sees masks (#114.1).
"""
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.makerspaces.models import (
    ImportedMember, MakerspaceMembership, MembershipErasureRequest, MembershipInviteLink, MembershipRecord,
    MembershipTitle, MembershipTitleAssignment,
)
from apps.makerspaces.models_membership_rules import TITLE_COLOURS


class MembershipRecordSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    source = serializers.CharField(source="membership.source", read_only=True)
    member_number = serializers.SerializerMethodField()

    class Meta:
        model = MembershipRecord
        fields = ("state_code", "gstin", "staff_notes", "source", "member_number", "updated_at")
        read_only_fields = ("source", "member_number", "updated_at")

    def get_member_number(self, obj) -> str:
        from apps.makerspaces.membership_number import display_number
        return display_number(obj.membership)


class MembershipRecordInputSerializer(serializers.Serializer):
    state_code = serializers.CharField(max_length=2, required=False, allow_blank=True)
    gstin = serializers.CharField(max_length=15, required=False, allow_blank=True)
    staff_notes = serializers.CharField(max_length=4000, required=False, allow_blank=True)


class MembershipTitleSerializer(serializers.ModelSerializer):
    colour = serializers.ChoiceField(choices=[key for key, _ in TITLE_COLOURS], required=False, allow_blank=True)

    class Meta:
        model = MembershipTitle
        fields = ("id", "name", "colour", "sort_order", "archived_at", "created_at", "updated_at")
        read_only_fields = ("id", "archived_at", "created_at", "updated_at")


class TitleAssignmentSerializer(serializers.ModelSerializer):
    title = MembershipTitleSerializer(read_only=True)

    class Meta:
        model = MembershipTitleAssignment
        fields = ("id", "title", "is_primary", "created_at")
        read_only_fields = fields


class TitleAssignInputSerializer(serializers.Serializer):
    title_id = serializers.IntegerField()
    primary = serializers.BooleanField(required=False, default=False)


class InviteLinkSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True, default="")
    live = serializers.SerializerMethodField()

    class Meta:
        model = MembershipInviteLink
        fields = ("id", "label", "plan", "plan_name", "unit", "max_uses", "uses", "expires_at", "revoked_at", "live",
                  "created_at")
        read_only_fields = fields

    def get_live(self, obj) -> bool:
        from django.utils import timezone
        return obj.live(timezone.now())


class InviteLinkCreateSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=120, required=False, allow_blank=True)
    plan_id = serializers.IntegerField(required=False, allow_null=True)
    unit_id = serializers.IntegerField(required=False, allow_null=True)  # parity O-B1
    max_uses = serializers.IntegerField(min_value=1, max_value=10000, required=False, default=1)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class InviteLinkCreatedSerializer(InviteLinkSerializer):
    # The clear code is shown exactly once, at creation; only its digest is stored.
    code = serializers.CharField(read_only=True)

    class Meta(InviteLinkSerializer.Meta):
        fields = (*InviteLinkSerializer.Meta.fields, "code")
        read_only_fields = fields


class WorklistRowSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    """One membership on the renewal desk; the term facts ride on `_desk` (set by the view)."""
    pii_account_fields = ("name", "email")
    name = serializers.CharField(source="user.display_name", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    member_number = serializers.SerializerMethodField()
    desk = serializers.SerializerMethodField()

    class Meta:
        model = MakerspaceMembership
        fields = ("id", "name", "email", "member_number", "desk")
        read_only_fields = fields

    def get_member_number(self, obj) -> str:
        from apps.makerspaces.membership_number import formatted
        return formatted(obj.member_number, self.context.get("pattern", ""), obj.created_at.year)

    def get_desk(self, obj) -> dict:
        row = obj._desk
        term = row["term"]
        return {"term_id": term.pk, "plan_id": term.plan_id, "plan_name": term.plan.name,
                "ends_at": term.ends_at, "grace_ends_at": row["grace_ends_at"], "standing": row["standing"],
                "renewal_payment_status": term.renewal_payment.status if term.renewal_payment_id else "",
                "reminded_today": row["reminded_today"]}


class MembershipIdsSerializer(serializers.Serializer):
    membership_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=200)


class ExtendInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
    days = serializers.IntegerField(min_value=1, max_value=3650, required=False)
    until = serializers.DateField(required=False)


class BulkDecideInputSerializer(serializers.Serializer):
    request_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=100)
    decision = serializers.ChoiceField(choices=("approve", "reject"))
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class BulkDecideResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ok = serializers.BooleanField()
    code = serializers.CharField(allow_blank=True)


class StaffErasureSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    pii_account_fields = ("member_name", "member_email")
    member_name = serializers.CharField(source="membership.user.display_name", read_only=True)
    member_email = serializers.CharField(source="membership.user.email", read_only=True)

    class Meta:
        model = MembershipErasureRequest
        fields = ("id", "membership", "member_name", "member_email", "status", "member_note", "decision_note",
                  "created_at", "decided_at")
        read_only_fields = fields


class ErasureDecisionInputSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ImportedMemberSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True, default="")

    class Meta:
        model = ImportedMember
        fields = ("id", "status", "name", "email", "phone", "external_number", "plan", "plan_name", "starts_on",
                  "ends_on", "created_at", "accepted_at")
        read_only_fields = fields
