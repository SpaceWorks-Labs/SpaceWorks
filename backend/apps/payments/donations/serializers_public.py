"""Public and giver-facing shapes. Nothing here names another person or carries a PAN."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from .tax_receipts import mask_pan


class GiverFields(serializers.Serializer):
    """A guest's identity (ignored for a signed-in giver) and the optional tax-receipt request."""

    donor_name = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    donor_email = serializers.EmailField(required=False, allow_blank=True, default="")
    email_code = serializers.CharField(required=False, allow_blank=True, max_length=12, default="")
    wants_tax_receipt = serializers.BooleanField(required=False, default=False)
    donor_pan = serializers.CharField(required=False, allow_blank=True, max_length=12, default="",
                                      help_text="Only with an India 80G request. Stored encrypted; never shown back in full.")
    donor_address = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


class DonationCreateSerializer(GiverFields):
    amount = MoneyField(max_digits=13, decimal_places=3)
    campaign = serializers.IntegerField(required=False, allow_null=True, default=None)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    recognize_publicly = serializers.BooleanField(
        required=False, default=False, help_text="Name me among the campaign's supporters. Off: anonymous.")


class PledgeCreateSerializer(GiverFields):
    amount = MoneyField(max_digits=13, decimal_places=3)
    interval = serializers.ChoiceField(choices=("monthly", "quarterly", "yearly"))
    starts_on = serializers.DateField(required=False, allow_null=True, default=None)
    campaign = serializers.IntegerField(required=False, allow_null=True, default=None)


class EmailCodeSerializer(serializers.Serializer):
    donor_email = serializers.EmailField()


class CampaignCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    description = serializers.CharField()
    goal_amount = MoneyField(max_digits=13, decimal_places=3, allow_null=True)
    raised_amount = MoneyField(max_digits=15, decimal_places=3)
    currency = serializers.CharField()
    starts_at = serializers.DateTimeField(allow_null=True)
    ends_at = serializers.DateTimeField(allow_null=True)
    supporter_count = serializers.IntegerField()
    supporters = serializers.ListField(child=serializers.CharField(), help_text="Only givers who chose to be named.")


class ExemptionCardSerializer(serializers.Serializer):
    scheme = serializers.CharField()
    label = serializers.CharField()
    number = serializers.CharField()


class NonprofitSerializer(serializers.Serializer):
    is_nonprofit = serializers.BooleanField()
    legal_name = serializers.CharField(allow_blank=True)
    registration_number = serializers.CharField(allow_blank=True)
    exemptions = ExemptionCardSerializer(many=True)


class DonationPageSerializer(serializers.Serializer):
    makerspace = serializers.CharField()
    intro = serializers.CharField(allow_blank=True)
    currency = serializers.CharField()
    minimum_amount = MoneyField(max_digits=13, decimal_places=3)
    suggested_amounts = serializers.ListField(child=serializers.CharField())
    campaigns = CampaignCardSerializer(many=True)
    online_available = serializers.BooleanField()
    recurring_available = serializers.BooleanField()
    tax_receipts_available = serializers.BooleanField()
    tax_registration_number = serializers.CharField(allow_blank=True)
    tax_schemes = serializers.ListField(child=serializers.CharField())
    tax_receipt_needs_pan = serializers.BooleanField(help_text="India 80G asks for the giver's PAN and address.")
    receipt_note = serializers.CharField(allow_blank=True, help_text="Set when gifts here get no tax receipt.")
    nonprofit = NonprofitSerializer()
    guest_allowed = serializers.BooleanField()


class OfflineSerializer(serializers.Serializer):
    instructions = serializers.CharField(allow_blank=True)
    upi = serializers.JSONField(allow_null=True)
    claimable = serializers.BooleanField()


class GiftStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    makerspace = serializers.CharField()
    campaign = serializers.CharField(allow_blank=True)
    amount = MoneyField(max_digits=13, decimal_places=3)
    currency = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    paid_at = serializers.DateTimeField(allow_null=True)
    receipt_number = serializers.CharField(allow_blank=True)
    tax_receipt_number = serializers.CharField(allow_blank=True)
    receipt_note = serializers.CharField(allow_blank=True, help_text="'Not a tax receipt' when none was issued.")
    donor_pan_masked = serializers.CharField(allow_blank=True)
    online_available = serializers.BooleanField()
    checkout_url = serializers.CharField(allow_blank=True)
    status_token = serializers.CharField(allow_blank=True, help_text="Guests only: the signed link to this page.")
    offline = OfflineSerializer(allow_null=True)


class PledgeStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    makerspace = serializers.CharField()
    campaign = serializers.CharField(allow_blank=True)
    amount = MoneyField(max_digits=13, decimal_places=3)
    currency = serializers.CharField()
    interval = serializers.CharField()
    status = serializers.CharField()
    starts_on = serializers.DateField()
    next_due_on = serializers.DateField()
    donor_pan_masked = serializers.CharField(allow_blank=True)
    manage_token = serializers.CharField(allow_blank=True, help_text="Guests only: the signed manage link.")


class PledgeActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("pause", "resume", "cancel", "update"))
    amount = MoneyField(max_digits=13, decimal_places=3, required=False, allow_null=True,
                                      default=None)
    interval = serializers.ChoiceField(choices=("monthly", "quarterly", "yearly"), required=False, allow_null=True,
                                       default=None)


class SponsorCardSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    tier = serializers.CharField(allow_blank=True)
    logo_url = serializers.CharField(allow_blank=True)
    website_url = serializers.CharField(allow_blank=True)
    blurb = serializers.CharField(allow_blank=True)


class SponsorWallSerializer(serializers.Serializer):
    results = SponsorCardSerializer(many=True)


def gift_status(donation, *, payment=None, token="", checkout=""):
    """The giver's own view of one gift (guest status page and member list)."""
    from apps.makerspaces.platform import feature_enabled
    from apps.payments.availability import online_payments_enabled_for

    from .tax_receipts import payment_for, receipt_note

    payment = payment or payment_for(donation)
    receipt = ""
    if payment is not None:
        receipt = payment.documents.filter(kind="receipt", reverses__isnull=True).order_by("pk").values_list(
            "number", flat=True).first() or ""
    pending = payment is not None and payment.status == "pending"
    offline = None
    if pending:
        from apps.payments.payment_rows_l5 import offline_collection
        offline = offline_collection(payment)
    return {
        "id": donation.pk, "makerspace": donation.makerspace.name,
        "campaign": donation.campaign.name if donation.campaign_id else "", "amount": donation.amount,
        "currency": donation.currency, "status": donation.status, "payment_status": payment.status if payment else "",
        "created_at": donation.created_at, "paid_at": donation.paid_at, "receipt_number": receipt,
        "tax_receipt_number": (donation.tax_receipt or {}).get("number", "")
        if feature_enabled(donation.makerspace, "finance.tax_exempt_receipts") else "",
        "receipt_note": receipt_note(donation),
        "donor_pan_masked": mask_pan(donation.tax_detail.pan) if donation.tax_detail_id else "",
        "online_available": pending and online_payments_enabled_for(payment), "checkout_url": checkout,
        "status_token": token, "offline": offline,
    }
