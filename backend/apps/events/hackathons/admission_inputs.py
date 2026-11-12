"""Frozen §12A.1 boundary: admission fields are distinct from form answers."""
from django.utils.translation import gettext
from dataclasses import dataclass, field
from rest_framework import serializers
from .admission_errors import fail


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            fail("invalid_input", gettext("Expected an object."), status=400)
        unknown = set(data) - self.fields.keys()
        if unknown:
            fail("unknown_fields", gettext("Remove unsupported fields."), status=400,
                 fields={key: ["Unknown field."] for key in sorted(unknown)})
        return super().to_internal_value(data)


class LiteralBoolean(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid", input=data)
        return data


class CommandInput(StrictSerializer):
    operation_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)


class CocInput(StrictSerializer):
    revision = serializers.IntegerField(min_value=1)
    accepted = LiteralBoolean()


class OptionalConsents(StrictSerializer):
    mlh_data_sharing = LiteralBoolean(required=False, default=False)


class ApplicationInput(CommandInput):
    form = serializers.JSONField(required=False)
    answers = serializers.DictField(required=False)
    derivations = serializers.DictField(required=False)
    save_choices = serializers.DictField(child=LiteralBoolean(), required=False)
    saved_detail_versions = serializers.DictField(child=serializers.IntegerField(min_value=0), required=False)
    event_date_revision = serializers.IntegerField(min_value=1, required=False)
    coc = CocInput(required=False)
    optional_consents = OptionalConsents(required=False)
    ticket_type_id = serializers.IntegerField(min_value=1, required=False)
    invite_code = serializers.CharField(max_length=128, allow_blank=False, required=False, write_only=True)
    promo_code = serializers.CharField(max_length=128, allow_blank=False, required=False, write_only=True)
    email = serializers.EmailField(max_length=254, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=64, allow_blank=True, required=False)
    host_waiver_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    host_waiver_version = serializers.CharField(max_length=64, allow_blank=False, allow_null=True, required=False)
    host_waiver_accepted = LiteralBoolean(required=False)
    stage_forms = serializers.ListField(child=serializers.DictField(), max_length=50, required=False)
    reimbursement_request = serializers.DictField(required=False)

    def to_internal_value(self, data):
        if isinstance(data, dict) and "custom_answers" in data:
            fail("answer_field_conflict", gettext("Use the application answers field."), status=400,
                 fields={"custom_answers": ["Use answers."]})
        if self.context.get("draft") and isinstance(data, dict) and any(k in data for k in ("invite_code", "promo_code")):
            fail("admission_code_submit_only", gettext("Apply codes when submitting."), status=400,
                 fields={k: ["Submit only."] for k in ("invite_code", "promo_code") if k in data})
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError as exc:
            fail("invalid_admission_input", gettext("Review the admission fields."), status=400, fields=exc.detail)


ADMISSION_FIELDS = (
    "ticket_type_id", "invite_code", "promo_code", "email", "phone",
    "host_waiver_id", "host_waiver_version", "host_waiver_accepted",
)


@dataclass(frozen=True)
class AdmissionSelection:
    values: dict = field(repr=False)

    def draft_values(self):
        # Proposed waiver selection never constitutes acceptance evidence.
        return {k: v for k, v in self.values.items() if k not in ("invite_code", "promo_code")}


def typed_admission_input(payload, *, draft=False):
    serializer = ApplicationInput(data=payload, context={"draft": draft})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    return data, AdmissionSelection({k: data[k] for k in ADMISSION_FIELDS if k in data})


def effective_contacts(actor, selection, *, required=True):
    email = (actor.email or selection.values.get("email") or "").strip().lower()
    phone = (actor.phone or selection.values.get("phone") or "").strip()
    if required and (not email or not phone):
        fail("contact_required", gettext("Provide an email address and phone number."), status=400,
             fields={k: ["Required."] for k, v in (("email", email), ("phone", phone)) if not v})
    # Account values are authoritative but still must meet registration bounds.
    field = serializers.EmailField(max_length=254)
    if email:
        email = field.run_validation(email)
    if len(phone) > 64:
        fail("invalid_contact", gettext("Phone number is too long."), status=400, fields={"phone": ["At most 64 characters."]})
    return {"email": email, "phone": phone}
