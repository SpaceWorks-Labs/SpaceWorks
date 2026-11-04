"""ID-programme serializers. Holder name/email/answers/reasons are scoped PII: masked for a
superadmin without a PII window, and masked for VIEW-only staff (SPEC §9)."""
from rest_framework import serializers

from apps.accounts import rbac
from apps.accounts.pii_presentation import PiiMaskingSerializerMixin

from .models import IdProgramme, IdProgrammeCard

MASK = "••••"


class IdProgrammeSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)

    class Meta:
        model = IdProgramme
        fields = ("id", "organization", "organization_slug", "makerspace", "name", "slug", "description", "status",
                  "registration_open",
                  "requires_approval", "id_prefix", "next_sequence", "validity_mode", "valid_until", "validity_days",
                  "photo_mode", "form_schema", "public_verify", "email_daily_cap", "counts", "can_manage",
                  "created_at", "updated_at")
        read_only_fields = ("id", "organization", "organization_slug", "makerspace", "slug", "next_sequence", "counts",
                            "can_manage",
                            "created_at", "updated_at")

    def get_counts(self, obj) -> dict:
        from django.db.models import Count
        rows = dict(obj.cards.values_list("status").annotate(total=Count("id")))
        return {"all": sum(rows.values()), **{key: rows.get(key, 0) for key in ("pending", "approved", "rejected",
                                                                                   "revoked")}}

    def get_can_manage(self, obj) -> bool:
        request = self.context.get("request")
        return rbac.can(getattr(request, "user", None), rbac.Action.MANAGE_ID_PROGRAMMES, obj.makerspace_id)


class IdProgrammeCreateSerializer(serializers.Serializer):
    makerspace_id = serializers.IntegerField()
    name = serializers.CharField(min_length=2, max_length=80)
    preset = serializers.ChoiceField(choices=("", "students", "volunteers", "staff"), required=False, default="")


class IdProgrammeCardSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    linked = serializers.SerializerMethodField()
    photo_set = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()

    class Meta:
        model = IdProgrammeCard
        fields = ("id", "programme", "name", "email", "answers", "status", "status_reason", "source", "id_number",
                  "issued_at", "expires_at", "revoked_at", "last_emailed_at", "linked", "photo_set", "created_at")
        read_only_fields = fields

    def get_linked(self, obj) -> bool:
        return obj.user_id is not None

    def get_photo_set(self, obj) -> bool:
        return bool(obj.photo_object_key)

    def get_answers(self, obj) -> dict:
        from .holders import answers
        return answers(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        if not rbac.can(viewer, rbac.Action.MANAGE_ID_PROGRAMMES, instance.makerspace_id):
            # VIEW_ID_PROGRAMMES sees who is in the programme, never their contact or answers.
            data.update(email=MASK, answers={}, status_reason="")
            data["pii_masked"] = True
        return data


class IdProgrammeCardCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)


class IdProgrammeCardEditSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)


class DecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("approve", "reject", "revoke", "reinstate", "renew"))
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=500)
    all = serializers.BooleanField(default=False)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)


class ImportPreviewSerializer(serializers.Serializer):
    content = serializers.CharField(help_text="The CSV file's text (UTF-8, up to 2 MB).")


class ImportCommitSerializer(ImportPreviewSerializer):
    mapping = serializers.DictField(child=serializers.IntegerField(allow_null=True))
    approve = serializers.BooleanField(default=False)
    dry_run = serializers.BooleanField(default=False)


class JoinSerializer(serializers.Serializer):
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    photo_object_key = serializers.CharField(max_length=300, required=False, allow_blank=True)
    photo_consent = serializers.BooleanField(default=False)


class PublicProgrammeSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name")
    questions = serializers.SerializerMethodField()

    class Meta:
        model = IdProgramme
        fields = ("name", "slug", "description", "organization_name", "photo_mode", "requires_approval",
                  "registration_open", "questions")
        read_only_fields = fields

    def get_questions(self, obj) -> list:
        return [{key: question[key] for key in ("key", "label", "type", "required", "options")}
                for question in obj.form_schema or ()]
