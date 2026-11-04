"""Staff shapes for donations, campaigns, pledges and settings (finance staff only).

Donor contact fields are scoped PII and adopt `PiiMaskingSerializerMixin` (#114.1): a
superadmin without a PII window reads them masked. The PAN is never returned in full here --
only `donor_pan_masked` (last four), itself masked for that superadmin.
"""

from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.payments.serializers_reconciliation import ManualSettlementSerializer

from .models import Donation, DonationCampaign, DonationPledge, DonationSettings
from .tax_receipts import mask_pan


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = DonationCampaign
        fields = ("id", "kind", "name", "slug", "description", "goal_amount", "currency", "starts_at", "ends_at",
                  "is_active", "is_public", "created_at", "updated_at")
        read_only_fields = ("id", "currency", "created_at", "updated_at")


class DonationSettingsSerializer(serializers.ModelSerializer):
    suggested_amounts = serializers.ListField(child=serializers.DecimalField(max_digits=12, decimal_places=2),
                                              max_length=8, required=False)

    class Meta:
        model = DonationSettings
        fields = ("page_intro", "suggested_amounts", "minimum_amount", "tax_exempt_registration_number",
                  "tax_exempt_valid_from", "tax_exempt_valid_until", "tax_exempt_registrant_pan", "tax_exempt_note",
                  "updated_at")
        read_only_fields = ("updated_at",)

    def validate_tax_exempt_registrant_pan(self, value):
        from .tax_receipts import PAN_RE, normalize_pan

        value = normalize_pan(value)
        if value and not PAN_RE.match(value):
            raise serializers.ValidationError("Enter the institution's 10-character PAN.")
        return value

    def validate(self, data):
        start, end = data.get("tax_exempt_valid_from"), data.get("tax_exempt_valid_until")
        if start and end and end < start:
            raise serializers.ValidationError({"tax_exempt_valid_until": "The validity must end after it starts."})
        data["suggested_amounts"] = [str(value) for value in data.get("suggested_amounts", [])]
        return data


class DonationSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    campaign_name = serializers.CharField(source="campaign.name", default="", read_only=True)
    payment_id = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    donor_pan_masked = serializers.SerializerMethodField()
    tax_receipt_number = serializers.SerializerMethodField()
    is_guest = serializers.SerializerMethodField()
    pii_account_fields = ("donor_pan_masked",)

    class Meta:
        model = Donation
        fields = ("id", "campaign", "campaign_name", "pledge", "period_start", "donor", "is_guest", "donor_name",
                  "donor_email", "donor_note", "amount", "currency", "source", "status", "wants_tax_receipt",
                  "donor_pan_masked", "donor_address", "tax_receipt_number", "payment_id", "payment_status",
                  "created_at", "paid_at", "cancelled_at")

    def _payment(self, obj):
        return (self.context.get("payments") or {}).get(obj.pk)

    def get_payment_id(self, obj) -> int | None:
        payment = self._payment(obj)
        return payment.pk if payment else None

    def get_payment_status(self, obj) -> str:
        payment = self._payment(obj)
        return payment.status if payment else ""

    def get_donor_pan_masked(self, obj) -> str:
        return mask_pan(obj.donor_pan) if obj.wants_tax_receipt else ""

    def get_tax_receipt_number(self, obj) -> str:
        return (obj.tax_receipt or {}).get("number", "")

    def get_is_guest(self, obj) -> bool:
        return obj.donor_id is None


class PledgeSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    campaign_name = serializers.CharField(source="campaign.name", default="", read_only=True)
    donor_pan_masked = serializers.SerializerMethodField()
    pii_account_fields = ("donor_pan_masked",)

    class Meta:
        model = DonationPledge
        fields = ("id", "campaign", "campaign_name", "donor", "donor_name", "donor_email", "amount", "currency",
                  "interval", "starts_on", "next_due_on", "ends_on", "status", "wants_tax_receipt",
                  "donor_pan_masked", "created_at", "cancelled_at")

    def get_donor_pan_masked(self, obj) -> str:
        return mask_pan(obj.donor_pan) if obj.wants_tax_receipt else ""


class DeskGiftSerializer(serializers.Serializer):
    """A gift received in person: who gave (optional account), the amount and the receipt."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    donor_name = serializers.CharField(max_length=200)
    donor_email = serializers.EmailField(required=False, allow_blank=True, default="")
    campaign = serializers.IntegerField(required=False, allow_null=True, default=None)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    wants_tax_receipt = serializers.BooleanField(required=False, default=False)
    donor_pan = serializers.CharField(required=False, allow_blank=True, max_length=12, default="")
    donor_address = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    settlement = ManualSettlementSerializer()


class NoteSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


def pledge_status(pledge, *, token=""):
    return {"id": pledge.pk, "makerspace": pledge.makerspace.name,
            "campaign": pledge.campaign.name if pledge.campaign_id else "", "amount": pledge.amount,
            "currency": pledge.currency, "interval": pledge.interval, "status": pledge.status,
            "starts_on": pledge.starts_on, "next_due_on": pledge.next_due_on,
            "donor_pan_masked": mask_pan(pledge.donor_pan) if pledge.wants_tax_receipt else "",
            "manage_token": token}
