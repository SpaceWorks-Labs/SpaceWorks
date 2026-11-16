"""Staff shapes for donations, campaigns, pledges and settings (finance staff only).

Donor contact fields are scoped PII and adopt `PiiMaskingSerializerMixin` (#114.1): a
superadmin without a PII window reads them masked. The PAN is never returned in full here --
only `donor_pan_masked` (last four), itself masked for that superadmin.
"""

from django.utils.translation import gettext
from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin
from apps.payments.serializers_reconciliation import ManualSettlementSerializer

from .models import Donation, DonationCampaign, DonationPledge, DonationSettings
from .nonprofit import SCHEMES, clean_exemptions
from .tax_receipts import mask_pan


class CampaignSerializer(serializers.ModelSerializer):
    raised_amount = serializers.SerializerMethodField(help_text="Received gifts, in the campaign's currency.")

    class Meta:
        model = DonationCampaign
        fields = ("id", "kind", "name", "slug", "description", "goal_amount", "raised_amount", "currency",
                  "starts_at", "ends_at", "is_active", "is_public", "created_at", "updated_at")
        read_only_fields = ("id", "currency", "raised_amount", "created_at", "updated_at")

    def get_raised_amount(self, obj) -> str:
        from .views_public import raised

        return str(raised(obj)) if obj.pk else "0.00"


class TaxExemptionSerializer(serializers.Serializer):
    """One tax-exemption registration of the non-profit profile (decision 242(m))."""

    scheme = serializers.ChoiceField(choices=sorted(SCHEMES))
    number = serializers.CharField(max_length=64)
    valid_from = serializers.CharField(allow_blank=True, required=False, help_text="YYYY-MM-DD or blank.")
    valid_until = serializers.CharField(allow_blank=True, required=False, help_text="YYYY-MM-DD or blank.")


class DonationSettingsSerializer(serializers.ModelSerializer):
    """Page text, amounts and the non-profit profile. The single-80G columns are a read-only mirror
    of the list's first India 80G entry (`nonprofit.mirror_legacy_80g`)."""

    suggested_amounts = serializers.ListField(child=MoneyField(max_digits=13, decimal_places=3),
                                              max_length=8, required=False)
    # A ListField (not `many=True`) so ModelSerializer stores it as the JSON column it is.
    tax_exemptions = serializers.ListField(child=TaxExemptionSerializer(), max_length=10, required=False)

    class Meta:
        model = DonationSettings
        fields = ("page_intro", "suggested_amounts", "minimum_amount", "is_nonprofit", "legal_name",
                  "organization_registration_number", "tax_exemptions", "signatory_name", "signatory_title",
                  "receipt_footer", "tax_exempt_registration_number", "tax_exempt_valid_from",
                  "tax_exempt_valid_until", "tax_exempt_registrant_pan", "tax_exempt_note", "updated_at")
        read_only_fields = ("tax_exempt_registration_number", "tax_exempt_valid_from", "tax_exempt_valid_until",
                            "updated_at")

    def validate_tax_exemptions(self, value):
        return clean_exemptions([dict(row) for row in value])

    def validate_tax_exempt_registrant_pan(self, value):
        from .tax_receipts import PAN_RE, normalize_pan

        value = normalize_pan(value)
        if value and not PAN_RE.match(value):
            raise serializers.ValidationError(gettext("Enter the institution's 10-character PAN."))
        return value

    def validate(self, data):
        if "suggested_amounts" in data or self.instance is None or not self.partial:
            data["suggested_amounts"] = [str(value) for value in data.get("suggested_amounts", [])]
        if data.get("tax_exemptions") == []:
            # An emptied list also empties its old 80G mirror, which would otherwise be adopted back.
            data.update(tax_exempt_registration_number="", tax_exempt_valid_from=None, tax_exempt_valid_until=None)
        return data


class DonationSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    campaign_name = serializers.CharField(source="campaign.name", default="", read_only=True)
    payment_id = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    donor_pan_masked = serializers.SerializerMethodField()
    tax_receipt_number = serializers.SerializerMethodField()
    is_guest = serializers.SerializerMethodField()
    donor_address = serializers.SerializerMethodField()
    open_claim = serializers.SerializerMethodField()
    pii_account_fields = ("donor_pan_masked", "donor_address")

    class Meta:
        model = Donation
        fields = ("id", "campaign", "campaign_name", "pledge", "period_start", "donor", "is_guest", "donor_name",
                  "donor_email", "donor_note", "amount", "currency", "source", "status", "wants_tax_receipt",
                  "donor_pan_masked", "donor_address", "tax_receipt_number", "payment_id", "payment_status",
                  "recognize_publicly", "open_claim", "created_at", "paid_at", "cancelled_at")

    def get_open_claim(self, obj) -> dict | None:
        """The giver's open "I've paid" claim (reference and date), decided in the Donations area."""
        claim = (self.context.get("claims") or {}).get(obj.pk)
        return {"id": claim.pk, "reference": claim.reference, "paid_on": claim.paid_on,
                "status": claim.status} if claim else None

    def _payment(self, obj):
        return (self.context.get("payments") or {}).get(obj.pk)

    def get_payment_id(self, obj) -> int | None:
        payment = self._payment(obj)
        return payment.pk if payment else None

    def get_payment_status(self, obj) -> str:
        payment = self._payment(obj)
        return payment.status if payment else ""

    def get_donor_pan_masked(self, obj) -> str:
        return mask_pan(obj.tax_detail.pan) if obj.tax_detail_id else ""

    def get_donor_address(self, obj) -> str:
        return obj.tax_detail.address if obj.tax_detail_id else ""

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
        return mask_pan(obj.tax_detail.pan) if obj.tax_detail_id else ""


class DeskGiftSerializer(serializers.Serializer):
    """A gift received in person: who gave (optional account), the amount and the receipt."""

    amount = MoneyField(max_digits=13, decimal_places=3)
    donor_name = serializers.CharField(max_length=200)
    donor_email = serializers.EmailField(required=False, allow_blank=True, default="")
    campaign = serializers.IntegerField(required=False, allow_null=True, default=None)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    wants_tax_receipt = serializers.BooleanField(required=False, default=False)
    donor_pan = serializers.CharField(required=False, allow_blank=True, max_length=12, default="")
    donor_address = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    recognize_publicly = serializers.BooleanField(required=False, default=False,
                                                  help_text="The giver agreed to be named on the campaign page.")
    settlement = ManualSettlementSerializer()


class NoteSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


def pledge_status(pledge, *, token=""):
    return {"id": pledge.pk, "makerspace": pledge.makerspace.name,
            "campaign": pledge.campaign.name if pledge.campaign_id else "", "amount": pledge.amount,
            "currency": pledge.currency, "interval": pledge.interval, "status": pledge.status,
            "starts_on": pledge.starts_on, "next_due_on": pledge.next_due_on,
            "donor_pan_masked": mask_pan(pledge.tax_detail.pan) if pledge.tax_detail_id else "",
            "manage_token": token}
