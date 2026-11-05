"""Hack-money closed inputs and reads for prize splits, claims, outcomes and prize visibility."""

from decimal import Decimal

from rest_framework import serializers

from .serializers import ClosedSerializer, CommandInput

MONEY = dict(max_digits=12, decimal_places=2)
METHODS = ("cash", "upi", "bank_transfer", "card", "cheque", "online", "other")


class ShareRow(ClosedSerializer):
    member_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(**MONEY, min_value=Decimal("0.01"))


class SplitInput(CommandInput):
    shares = ShareRow(many=True, min_length=1, max_length=50)


class ShareRespondInput(CommandInput):
    pass


class ClaimInput(CommandInput):
    country = serializers.RegexField(r"^[A-Z]{2}$")
    method = serializers.ChoiceField(choices=("bank_transfer", "upi", "paypal", "wise", "cash", "cheque", "other"))
    details = serializers.DictField(child=serializers.CharField(max_length=200, allow_blank=True))
    pan = serializers.CharField(max_length=12, allow_blank=True, required=False,
                                help_text="Optional Indian PAN for prize tax (#181). Encrypted; only ever shown masked.")


class RevealInput(CommandInput):
    reason_code = serializers.ChoiceField(choices=("pay_winner", "verify_details", "record_tax"))


class RevealRead(ClosedSerializer):
    share_id = serializers.IntegerField()
    country = serializers.CharField()
    method = serializers.CharField()
    details = serializers.DictField(child=serializers.CharField(allow_blank=True))
    pan = serializers.CharField(allow_blank=True)


class FulfilInput(CommandInput):
    method = serializers.ChoiceField(choices=("handed_over", "shipped", "sponsor_paid", "other"))
    reference = serializers.CharField(max_length=64, allow_blank=True, required=False,
                                      help_text="A tracking number or the sponsor's payment reference.")
    note = serializers.CharField(max_length=300, allow_blank=True, required=False)
    happened_on = serializers.DateField()


class ForfeitInput(CommandInput):
    share_id = serializers.IntegerField(min_value=1, required=False, allow_null=True,
                                        help_text="Forfeit one unpaid share; omit to forfeit the whole prize.")
    note = serializers.CharField(max_length=300)


class RecoveryResolveInput(CommandInput):
    outcome = serializers.ChoiceField(choices=("repaid", "waived"))
    method = serializers.ChoiceField(choices=METHODS, required=False)
    reference = serializers.CharField(max_length=64, allow_blank=True, required=False)
    receipt_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    note = serializers.CharField(max_length=300, allow_blank=True, required=False)
    happened_on = serializers.DateField()

    def validate(self, attrs):
        if attrs["outcome"] == "repaid" and not attrs.get("method"):
            raise serializers.ValidationError({"method": "Say how the money came back."})
        if attrs["outcome"] == "waived" and not attrs.get("note", "").strip():
            raise serializers.ValidationError({"note": "Say why the money is not being recovered."})
        return attrs


class ShareRead(ClosedSerializer):
    id = serializers.IntegerField()
    award_id = serializers.IntegerField()
    member_id = serializers.IntegerField(allow_null=True)
    amount = serializers.DecimalField(**MONEY)
    state = serializers.CharField()
    version = serializers.IntegerField()
    confirmed_at = serializers.DateTimeField(allow_null=True)


class AwardSplitRead(ClosedSerializer):
    award_id = serializers.IntegerField()
    prize_name = serializers.CharField()
    total = serializers.DecimalField(**MONEY, allow_null=True)
    shares = ShareRead(many=True)
    split_open = serializers.BooleanField()


class ClaimRead(ClosedSerializer):
    share_id = serializers.IntegerField(allow_null=True)
    version = serializers.IntegerField()
    state = serializers.ChoiceField(choices=("not_given", "submitted", "verified"))
    country = serializers.CharField(allow_blank=True)
    method = serializers.CharField(allow_blank=True)
    masked_details = serializers.CharField(allow_blank=True)
    pan_masked = serializers.CharField(allow_blank=True)
    verified = serializers.BooleanField()


class OutcomeRead(ClosedSerializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    award_id = serializers.IntegerField()
    share_id = serializers.IntegerField(allow_null=True)
    payout_id = serializers.IntegerField(allow_null=True)
    resolves_id = serializers.IntegerField(allow_null=True)
    kind = serializers.CharField()
    method = serializers.CharField(allow_blank=True)
    reference = serializers.CharField(allow_blank=True)
    amount = serializers.DecimalField(**MONEY, allow_null=True)
    currency = serializers.CharField(allow_blank=True)
    happened_on = serializers.DateField()
    note = serializers.CharField(allow_blank=True)
    ledger_entry_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class StaffClaimRow(ClaimRead):
    award_id = serializers.IntegerField()
    member_id = serializers.IntegerField(allow_null=True)
    amount = serializers.DecimalField(**MONEY)
    share_state = serializers.CharField()


class MyPrizeRead(ClosedSerializer):
    award_id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    event_title = serializers.CharField()
    prize_name = serializers.CharField()
    rank = serializers.IntegerField()
    kind = serializers.CharField()
    value_text = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    my_share = ShareRead(allow_null=True)
    my_payout = serializers.DictField(allow_null=True, help_text="gross, tds, net, currency, paid_on of my payout.")
    claim = ClaimRead(allow_null=True)
    claim_deadline = serializers.DateTimeField(allow_null=True)
    is_leader = serializers.BooleanField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class PublicPrizeRead(ClosedSerializer):
    name = serializers.CharField()
    track = serializers.CharField(allow_blank=True)
    sponsor = serializers.CharField(allow_blank=True)
    kind = serializers.CharField()
    value_text = serializers.CharField(allow_blank=True)
    amount_per_winner = serializers.DecimalField(**MONEY, allow_null=True)
    award_count = serializers.IntegerField()
    currency = serializers.CharField()


class PrizePoolRead(ClosedSerializer):
    currency = serializers.CharField()
    announced_total = serializers.DecimalField(**MONEY, help_text="Cash prizes the space pays, times their winners.")
    sponsor_funded = serializers.DecimalField(**MONEY, help_text="Paid sponsorship earmarked to this prize pool.")
    paid_gross = serializers.DecimalField(**MONEY)
    tds_recorded = serializers.DecimalField(**MONEY)
    owed = serializers.DecimalField(**MONEY, help_text="Announced awards with no standing payout or outcome.")
    recovered = serializers.DecimalField(**MONEY)
    sponsor_direct_awards = serializers.IntegerField()
