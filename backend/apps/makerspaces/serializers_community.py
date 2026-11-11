"""Decision 223 (k), lane L3b: serializers for minors, guardian consent, volunteer hours and the join funnel.

Outputs are plain `Serializer`s fed by the `*_payload` functions, so the schema documents every field and
no model attribute is exposed by accident. The date of birth is NEVER serialized (staff see an age or an
"under age" declaration); guardian contact details go to staff and to the guardian's own account only.
"""
from rest_framework import serializers

from apps.makerspaces.community_policy import POLICY_FIELDS
from apps.makerspaces.minors import age_of, current_consent
from apps.makerspaces.models import (
    CommunityPolicy, GuardianConsentTerms, MinorProfile, VolunteerCredit, VolunteerHourEntry,
)


class CommunityPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityPolicy
        fields = POLICY_FIELDS
        extra_kwargs = {name: {"required": False} for name in POLICY_FIELDS}


class GuardianTermsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuardianConsentTerms
        fields = ("id", "version", "body", "is_active", "created_at", "superseded_at")
        read_only_fields = fields


class GuardianTermsInputSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=64)
    body = serializers.CharField(max_length=20000)


class MinorRecordInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    user_email = serializers.EmailField(required=False)
    date_of_birth = serializers.CharField(required=False, allow_blank=True, max_length=10,
                                          help_text="YYYY-MM-DD. Leave blank and set declared_under_age instead.")
    declared_under_age = serializers.BooleanField(required=False, default=False)
    guardian_user_id = serializers.IntegerField(required=False, allow_null=True)
    guardian_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    guardian_email = serializers.EmailField(required=False, allow_blank=True)
    guardian_phone = serializers.CharField(required=False, allow_blank=True, max_length=32)

    def validate(self, attrs):
        if not (attrs.get("user_id") or attrs.get("user_email")):
            raise serializers.ValidationError({"user_id": "Name the person by id or e-mail."})
        return attrs


class ConsentInputSerializer(serializers.Serializer):
    signed_name = serializers.CharField(max_length=200)
    accepted = serializers.BooleanField()
    operation_id = serializers.CharField(required=False, allow_blank=True, max_length=64)


class ConsentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    terms_version = serializers.CharField()
    method = serializers.CharField()
    signed_at = serializers.DateTimeField()
    valid_until = serializers.DateTimeField()
    revoked_at = serializers.DateTimeField(allow_null=True)


class MinorProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    user_name = serializers.CharField()
    age = serializers.IntegerField(allow_null=True, help_text="Whole years; null when only 'under age' was declared.")
    declared_under_age = serializers.BooleanField()
    guardian_user_id = serializers.IntegerField(allow_null=True)
    guardian_name = serializers.CharField(allow_blank=True)
    guardian_email = serializers.CharField(allow_blank=True)
    guardian_phone = serializers.CharField(allow_blank=True)
    consent_state = serializers.ChoiceField(choices=("valid", "none"))
    consent_valid_until = serializers.DateTimeField(allow_null=True)
    consent_terms_version = serializers.CharField(allow_null=True)
    current_consent_id = serializers.IntegerField(allow_null=True, help_text="The live consent a staff member may revoke.")
    current_consent_version = serializers.CharField(allow_null=True)
    current_consent_signed_at = serializers.DateTimeField(allow_null=True)
    cleared_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class GuardianDependentSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField()
    dependent_name = serializers.CharField()
    consent_state = serializers.ChoiceField(choices=("valid", "none"))
    consent_valid_until = serializers.DateTimeField(allow_null=True)
    consents = ConsentSerializer(many=True)


class GuardianConsentPageSerializer(serializers.Serializer):
    terms = GuardianTermsSerializer(allow_null=True)
    dependents = GuardianDependentSerializer(many=True)


def user_name(user):
    return user.display_name or user.get_full_name() or user.username


def staff_minor_payload(profile):
    consent = current_consent(profile)
    return {"id": profile.pk, "user_id": profile.user_id, "user_name": user_name(profile.user),
            "age": age_of(profile), "declared_under_age": profile.declared_under_age,
            "guardian_user_id": profile.guardian_user_id, "guardian_name": profile.guardian_name,
            "guardian_email": profile.guardian_email, "guardian_phone": profile.guardian_phone,
            "consent_state": "valid" if consent else "none",
            "consent_valid_until": consent.valid_until if consent else None,
            "consent_terms_version": consent.terms_version if consent else None,
            "current_consent_id": consent.pk if consent else None,
            "current_consent_version": consent.terms_version if consent else None,
            "current_consent_signed_at": consent.signed_at if consent else None,
            "cleared_at": profile.cleared_at, "created_at": profile.created_at}


def dependent_payload(profile):
    consents = [{"id": c.pk, "terms_version": c.terms_version, "method": c.method, "signed_at": c.signed_at,
                 "valid_until": c.valid_until, "revoked_at": c.revoked_at}
                for c in profile.consents.all()[:20]]
    current = current_consent(profile)
    return {"profile_id": profile.pk, "dependent_name": user_name(profile.user),
            "consent_state": "valid" if current else "none",
            "consent_valid_until": current.valid_until if current else None, "consents": consents}


class VolunteerEntrySerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = VolunteerHourEntry
        fields = ("id", "member", "member_name", "minutes", "worked_on", "description", "source", "status",
                  "reviewed_at", "review_note", "created_at")
        read_only_fields = fields

    def get_member_name(self, obj) -> str:
        return user_name(obj.member)


class VolunteerLogInputSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(required=False, help_text="Staff only: the member the hours belong to.")
    minutes = serializers.IntegerField(min_value=1, max_value=1440)
    worked_on = serializers.DateField()
    description = serializers.CharField(required=False, allow_blank=True, max_length=200)


class VolunteerDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)


class VolunteerImportResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()


class VolunteerCreditSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = VolunteerCredit
        fields = ("id", "member", "member_name", "kind", "amount", "days", "currency", "status", "minutes_converted",
                  "applied_payment", "applied_amount", "applied_at", "created_at")
        read_only_fields = fields

    def get_member_name(self, obj) -> str:
        return user_name(obj.member)


class VoidInputSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=200)


class JoinPrefillSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    source = serializers.ChoiceField(choices=("event", "guest_pass"))
    source_ref = serializers.IntegerField()
    source_label = serializers.CharField()


class MinorProfileListSerializer(serializers.Serializer):
    results = MinorProfileSerializer(many=True)


def minors_queryset(makerspace):
    return MinorProfile.objects.filter(makerspace=makerspace).select_related("user").order_by("-created_at", "-pk")
