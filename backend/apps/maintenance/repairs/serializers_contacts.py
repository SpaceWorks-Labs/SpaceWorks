"""Technician directory payloads. Contact PII is masked for a superadmin without a window."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin

from .models_contacts import CHANNELS, TechnicianContact, TechnicianDefault


class TechnicianCoverageRowSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["machine_type", "inventory", "room"])
    id = serializers.IntegerField(required=False, allow_null=True)
    label = serializers.CharField(read_only=True)


class TechnicianConsentSerializer(serializers.Serializer):
    email = serializers.BooleanField()
    telegram = serializers.BooleanField()
    whatsapp = serializers.BooleanField()
    sms = serializers.BooleanField()


class TechnicianContactSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    person_id = serializers.IntegerField(read_only=True, allow_null=True)
    coverage = serializers.SerializerMethodField()
    consent = serializers.SerializerMethodField()
    opt_in_pending = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianContact
        fields = ["id", "kind", "person_id", "name", "email", "phone", "telegram_handle", "channels", "notes",
                  "is_archived", "coverage", "consent", "opt_in_pending", "created_at", "updated_at"]
        read_only_fields = fields

    @extend_schema_field(TechnicianCoverageRowSerializer(many=True))
    def get_coverage(self, row):
        out = []
        for item in row.coverage.all():
            target = item.machine_type if item.kind == "machine_type" else item.room
            out.append({"kind": item.kind, "id": getattr(target, "pk", None),
                        "label": getattr(target, "name", "") or "All inventory"})
        return out

    @extend_schema_field(TechnicianConsentSerializer)
    def get_consent(self, row):
        return {"email": bool(row.email or getattr(row.person, "email", "")),
                "telegram": bool(row.telegram_opted_in_at and row.telegram_chat_id),
                "whatsapp": bool(row.whatsapp_opted_in_at), "sms": bool(row.sms_opted_in_at)}

    def get_opt_in_pending(self, row) -> bool:
        from django.utils import timezone
        return bool(row.opt_in_expires_at and row.opt_in_expires_at > timezone.now())


class TechnicianContactWriteSerializer(serializers.Serializer):
    person_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    email = serializers.EmailField(required=False, allow_blank=True, max_length=254)
    phone = serializers.RegexField(r"^\+?[0-9 ()-]{0,31}$", required=False, allow_blank=True)
    telegram_handle = serializers.CharField(required=False, allow_blank=True, max_length=64)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    channels = serializers.ListField(child=serializers.ChoiceField(choices=list(CHANNELS)), required=False)
    coverage = TechnicianCoverageRowSerializer(many=True, required=False)


class TechnicianOptInLinkSerializer(serializers.Serializer):
    url = serializers.CharField()
    telegram_start = serializers.CharField()
    expires_at = serializers.DateTimeField()
    emailed = serializers.BooleanField()


class TechnicianConsentWithdrawSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=["telegram", "whatsapp", "sms"])


class TechnicianDefaultSerializer(serializers.ModelSerializer):
    contact_id = serializers.IntegerField()
    machine_type_id = serializers.IntegerField(allow_null=True, required=False)
    room_id = serializers.IntegerField(allow_null=True, required=False)

    class Meta:
        model = TechnicianDefault
        fields = ["id", "area", "machine_type_id", "room_id", "contact_id"]
        read_only_fields = ["id"]


class TechnicianOptInPageSerializer(serializers.Serializer):
    makerspace_name = serializers.CharField()
    technician_name = serializers.CharField()
    has_phone = serializers.BooleanField()
    consent = TechnicianConsentSerializer()
    telegram_start = serializers.CharField()


class TechnicianOptInAcceptSerializer(serializers.Serializer):
    channels = serializers.ListField(child=serializers.ChoiceField(choices=["whatsapp", "sms"]), min_length=1)
