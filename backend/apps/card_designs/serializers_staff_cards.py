"""Request/response shapes for the staff ID card routes (O-B4 part 2). Documentation + validation only."""
from rest_framework import serializers


class StaffRoleSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField(help_text="Translated name for a built-in role, the space's own name otherwise.")


class StaffCardSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    number = serializers.CharField()
    status = serializers.ChoiceField(choices=("valid", "revoked"))
    issued_at = serializers.DateTimeField()
    revoked_at = serializers.DateTimeField(allow_null=True)
    revoked_reason = serializers.CharField(allow_blank=True)
    print_count = serializers.IntegerField()
    check_url = serializers.CharField(allow_blank=True, help_text="Public check link; blank while the check page is off.")
    roles_changed_since_issue = serializers.BooleanField()


class StaffCardHolderSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    name = serializers.CharField()
    roles = StaffRoleSerializer(many=True)
    roles_text = serializers.CharField()
    machine_scope = serializers.CharField(allow_blank=True)
    eligible = serializers.BooleanField(help_text="False when the account is disabled or restricted.")
    card = StaffCardSummarySerializer(allow_null=True, help_text="The live card, or the latest revoked one.")


class StaffCardIssueSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField(min_value=1)


class StaffCardBulkIssueSerializer(serializers.Serializer):
    membership_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=200)


class StaffCardSkippedSerializer(serializers.Serializer):
    membership_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=("not_found", "quota", "already_issued", "not_eligible"))


class StaffCardBulkResultSerializer(serializers.Serializer):
    issued = StaffCardSummarySerializer(many=True)
    skipped = StaffCardSkippedSerializer(many=True)


class StaffCardReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=32, default="revoked")


class StaffCardNumberingSerializer(serializers.Serializer):
    prefix = serializers.CharField(allow_blank=True, max_length=6, required=False, default="")
    pattern = serializers.CharField(allow_blank=True, max_length=40, required=False, default="")


class StaffCardSettingsSerializer(serializers.Serializer):
    prefix = serializers.CharField(allow_blank=True)
    pattern = serializers.CharField()
    preview = serializers.ListField(child=serializers.CharField())
    auto_issue = serializers.BooleanField(help_text="`membership.staff_cards_auto_issue` for this space (read-only here).")
    desk_print = serializers.BooleanField(help_text="`membership.card_desk_print` for this space (read-only here).")


class StaffCardJobCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("bulk_sheet", "bulk_per_person", "zip"))
    card_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=1000,
                                     help_text="Omit to print every live staff card in the space.")
    paper = serializers.ChoiceField(choices=("a4", "letter", "per_card"), default="a4")
    order = serializers.ChoiceField(choices=("duplex", "fronts_then_backs"), default="duplex")
    crop_marks = serializers.BooleanField(default=True)
