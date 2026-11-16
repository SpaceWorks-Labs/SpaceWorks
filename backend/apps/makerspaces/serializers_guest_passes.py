"""Decision 223 serializers. Each audience gets its own shape so privacy is structural.

* Holder (`HolderPassSerializer`): their own pass, what it allows, the waiver step, the join prompt.
* Sponsor (`SponsorGuestSerializer`): the guest's DISPLAY NAME, the pass date, status and whether
  items are outstanding. Never the guest's contact details, other history or payments.
* Staff (`StaffPassSerializer`): the roster row for manage_members holders.
"""
from django.utils import timezone
from rest_framework import serializers

from apps.makerspaces.guest_pass_policy import POLICY_FIELDS
from apps.makerspaces.models import DayPassProduct, GuestPass, GuestPassPolicy
from django.utils.translation import gettext

MODES = {
    "borrow": GuestPassPolicy.Borrowing.values, "machines": GuestPassPolicy.Machines.values,
}


def display_name(user):
    if user is None:
        return ""
    return (user.get_full_name() or user.username or "").strip()


def effective_status(row, now=None):
    """Stored status, except a live pass past its window reads `expired` even before a sweep."""
    now = now or timezone.now()
    if row.status in GuestPass.LIVE_STATUSES and row.valid_until <= now:
        return GuestPass.Status.EXPIRED
    return row.status


def payment_status(row):
    if row.kind != GuestPass.Kind.DAY:  # "priced" = a charge exists, never the product's current amount
        return None
    from apps.payments.models import Payment
    return Payment.objects.filter(makerspace_id=row.makerspace_id, subject_id=row.pk,
                                  subject_type=Payment.SubjectType.GUEST_PASS).values_list("status", flat=True).first()


class _PassBase(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=GuestPass.Kind.choices)
    status = serializers.SerializerMethodField()
    valid_from = serializers.DateTimeField()
    valid_until = serializers.DateTimeField()

    def get_status(self, row) -> str:
        return effective_status(row)


class HolderPassSerializer(_PassBase):
    entitlements = serializers.JSONField()
    sponsor_name = serializers.SerializerMethodField()
    waiver_accepted = serializers.SerializerMethodField()
    waiver_required = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    wallet_platforms = serializers.SerializerMethodField()

    def get_wallet_platforms(self, row) -> list[str]:
        # Decision 223(k)/(l) hook (lane L4): which "Add to wallet" buttons this pass may show.
        from apps.card_designs.wallet.guest import platforms_for
        return platforms_for(row)

    def get_sponsor_name(self, row) -> str:
        return display_name(row.sponsor)

    def get_waiver_accepted(self, row) -> bool:
        return row.accepted_waiver_id is not None

    def get_waiver_required(self, row) -> bool:
        from apps.makerspaces.guest_pass_policy import policy_for
        from apps.makerspaces.models import MakerspaceWaiver
        return bool(policy_for(row.makerspace).waiver_required_on_site
                    and MakerspaceWaiver.objects.filter(makerspace_id=row.makerspace_id, is_active=True).exists())

    def get_payment_status(self, row) -> str | None:
        return payment_status(row)


class HolderPassListSerializer(serializers.Serializer):
    passes = HolderPassSerializer(many=True)
    visits_30d = serializers.IntegerField()
    join_threshold = serializers.IntegerField()
    should_prompt_join = serializers.BooleanField()


class SponsorGuestSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    guest_name = serializers.SerializerMethodField()
    pass_date = serializers.DateField()
    status = serializers.SerializerMethodField()
    items_outstanding = serializers.SerializerMethodField()

    def get_guest_name(self, row) -> str:
        return display_name(row.holder)

    def get_status(self, row) -> str:
        return effective_status(row)

    def get_items_outstanding(self, row) -> bool:
        from apps.hardware_requests.models import HardwareRequest
        return HardwareRequest.objects.filter(
            makerspace_id=row.makerspace_id, requester_id=row.holder_id, created_at__gte=row.valid_from,
            status__in=[HardwareRequest.Status.ISSUED, HardwareRequest.Status.PARTIALLY_RETURNED]).exists()


class SponsorInputSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    operation_id = serializers.CharField(max_length=64, required=False, allow_blank=False)


class SponsorResultSerializer(serializers.Serializer):
    detail = serializers.CharField()


class WaiverAcceptSerializer(serializers.Serializer):
    accepted = serializers.BooleanField()

    def validate_accepted(self, value):
        if value is not True:
            raise serializers.ValidationError(gettext("The waiver must be explicitly accepted."))
        return value


class RevokeInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class StaffPassSerializer(_PassBase):
    holder_id = serializers.IntegerField()
    holder_name = serializers.SerializerMethodField()
    holder_email = serializers.SerializerMethodField()
    sponsor_id = serializers.IntegerField(allow_null=True)
    sponsor_name = serializers.SerializerMethodField()
    product_id = serializers.IntegerField(allow_null=True)
    entitlements = serializers.JSONField()
    waiver_version = serializers.CharField(allow_null=True)
    waiver_accepted_at = serializers.DateTimeField(allow_null=True)
    payment_status = serializers.SerializerMethodField()
    revoked_at = serializers.DateTimeField(allow_null=True)
    revoked_reason = serializers.CharField()
    converted_membership_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()

    def get_holder_name(self, row) -> str:
        return display_name(row.holder)

    def get_holder_email(self, row) -> str:
        return row.holder.email or ""

    def get_sponsor_name(self, row) -> str:
        return display_name(row.sponsor)

    def get_payment_status(self, row) -> str | None:
        return payment_status(row)


class StaffIssueSerializer(serializers.Serializer):
    holder_email = serializers.EmailField(max_length=254, required=False)
    holder_id = serializers.IntegerField(required=False, min_value=1)
    sponsor_id = serializers.IntegerField(required=False, min_value=1)
    day = serializers.DateField(required=False)
    operation_id = serializers.CharField(max_length=64, required=False, allow_blank=False)

    def validate(self, attrs):
        if bool(attrs.get("holder_email")) == bool(attrs.get("holder_id")):
            raise serializers.ValidationError(gettext("Give exactly one of holder_email or holder_id."))
        return attrs


class DeskSaleSerializer(StaffIssueSerializer):
    product_id = serializers.IntegerField(min_value=1)
    sponsor_id = None


class PurchaseSerializer(serializers.Serializer):
    day = serializers.DateField(required=False)
    operation_id = serializers.CharField(max_length=64, required=False, allow_blank=False)


class PurchaseResultSerializer(serializers.Serializer):
    pass_id = serializers.IntegerField()
    status = serializers.CharField()
    payment_id = serializers.IntegerField(allow_null=True)
    payment_status = serializers.CharField(allow_null=True)
    amount = serializers.CharField()
    currency = serializers.CharField(allow_blank=True)


class DayPassProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayPassProduct
        fields = ["id", "name", "amount", "currency", "entitlements", "daily_cap", "is_public", "is_active",
                  "archived_at"]
        read_only_fields = ["id", "archived_at"]

    def validate_entitlements(self, value):
        if not isinstance(value, dict) or set(value) - {"borrow", "machines"}:
            raise serializers.ValidationError(gettext("Use only the keys borrow and machines."))
        for key, allowed in MODES.items():
            if key in value and value[key] not in allowed:
                raise serializers.ValidationError(gettext("%(key)s must be one of %(allowed)s.") % {"key": key, "allowed": allowed})
        return value


class PublicDayPassSerializer(serializers.ModelSerializer):
    """What a visitor sees: name and price. No cap, no sales count, no entitlements."""

    class Meta:
        model = DayPassProduct
        fields = ["id", "name", "amount", "currency"]


class GuestPassPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestPassPolicy
        fields = list(POLICY_FIELDS)
