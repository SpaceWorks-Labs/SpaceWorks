"""L21b closed inputs and reads: finalists, score-next, progress, prize payouts and programme options."""

from django.utils.translation import gettext
from decimal import Decimal

from rest_framework import serializers

from .serializers import ClosedSerializer, CommandInput, IdList, ResultEnvelope


class FinalistSelection(ClosedSerializer):
    source_round_id = serializers.IntegerField(min_value=1)
    target_round_id = serializers.IntegerField(min_value=1)
    selection = serializers.ChoiceField(choices=("top_n", "manual"))
    top_n = serializers.IntegerField(min_value=1, max_value=500, required=False)
    snapshot_ids = IdList(required=False)

    def validate(self, attrs):
        if attrs["selection"] == "top_n" and not attrs.get("top_n"):
            raise serializers.ValidationError({"top_n": gettext("Choose how many finalists advance.")})
        if attrs["selection"] == "manual" and not attrs.get("snapshot_ids"):
            raise serializers.ValidationError({"snapshot_ids": gettext("Pick at least one finalist.")})
        return attrs


class FinalistApplyInput(CommandInput, FinalistSelection):
    fingerprint = serializers.RegexField(r"^[0-9a-f]{64}$", help_text="The preview's fingerprint; 409 plan_changed when stale.")


class FinalistPublishInput(CommandInput):
    advance_id = serializers.IntegerField(min_value=1)


class FinalistRow(ClosedSerializer):
    snapshot_id = serializers.IntegerField()
    title = serializers.CharField()
    source_rank = serializers.IntegerField(allow_null=True)


class FinalistPreviewRead(ClosedSerializer):
    source_round_id = serializers.IntegerField()
    target_round_id = serializers.IntegerField()
    selection = serializers.CharField()
    top_n = serializers.IntegerField(allow_null=True)
    tied_at_cutoff = serializers.BooleanField()
    fingerprint = serializers.CharField()
    finalists = FinalistRow(many=True)


class FinalistAdvanceRead(ClosedSerializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    source_round_id = serializers.IntegerField()
    target_round_id = serializers.IntegerField()
    selection = serializers.CharField()
    top_n = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    current = serializers.BooleanField()
    published_at = serializers.DateTimeField(allow_null=True)
    finalists = FinalistRow(many=True)
    allowed_actions = serializers.ListField(child=serializers.CharField())


class NextProjectRead(ClosedSerializer):
    assignment_id = serializers.IntegerField(allow_null=True)
    snapshot_id = serializers.IntegerField(allow_null=True)
    reason = serializers.ChoiceField(choices=("started", "fewest_reviews", "none"))


class JudgeProgressRow(ClosedSerializer):
    judge_role_assignment_id = serializers.IntegerField()
    name = serializers.CharField()
    assigned = serializers.IntegerField()
    submitted = serializers.IntegerField()
    withdrawn = serializers.IntegerField()
    completion = serializers.IntegerField(help_text="Percent of live assignments submitted.")


class ProjectProgressRow(ClosedSerializer):
    snapshot_id = serializers.IntegerField()
    title = serializers.CharField()
    reviews = serializers.IntegerField()
    target = serializers.IntegerField()


class OutlierRow(ClosedSerializer):
    snapshot_id = serializers.IntegerField()
    judge_role_assignment_id = serializers.IntegerField()
    score = serializers.CharField(help_text="0-100 scale: (weighted 1-5 value - 1) x 25.")
    project_mean = serializers.CharField()
    rule = serializers.ChoiceField(choices=("two_sd", "spread_25"))


class StaleDraftRow(ClosedSerializer):
    assignment_id = serializers.IntegerField()
    judge_role_assignment_id = serializers.IntegerField()
    snapshot_id = serializers.IntegerField()
    saved_at = serializers.DateTimeField()


class ProgressRead(ClosedSerializer):
    round_id = serializers.IntegerField()
    state = serializers.CharField()
    mode = serializers.CharField()
    target = serializers.IntegerField()
    below_target = ProjectProgressRow(many=True)
    judges = JudgeProgressRow(many=True)
    outliers = OutlierRow(many=True)
    stale_drafts = StaleDraftRow(many=True)


class PayoutInput(CommandInput):
    award_id = serializers.IntegerField(min_value=1)
    recipient_id = serializers.IntegerField(min_value=1, required=False,
                                            help_text="A member of the winning team; defaults to the team leader.")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"), required=False)
    method = serializers.ChoiceField(choices=("cash", "upi", "bank_transfer", "card", "cheque", "online", "other"))
    reference = serializers.CharField(max_length=64, allow_blank=True, default="")
    paid_on = serializers.DateField()
    receipt_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    tds_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False,
                                          allow_null=True, help_text="Prize tax deducted (#181, record only). Omit "
                                          "to use the space's proposal; 0 records none.")


class PayoutReverseInput(CommandInput):
    reason = serializers.CharField(max_length=300)


class PayoutRead(ClosedSerializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    award_id = serializers.IntegerField(allow_null=True, help_text="Null for a People's choice payout (#181).")
    peoples_choice_standing_id = serializers.IntegerField(allow_null=True, required=False,
                                                         help_text="The People's choice winner paid, else null.")
    prize_id = serializers.IntegerField()
    prize_name = serializers.CharField()
    recipient_id = serializers.IntegerField(allow_null=True)
    kind = serializers.CharField()
    reverses_id = serializers.IntegerField(allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Gross: the ledger expense.")
    tds_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="What reached the winner.")
    currency = serializers.CharField()
    method = serializers.CharField()
    reference = serializers.CharField(allow_blank=True)
    paid_on = serializers.DateField()
    ledger_entry_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class PrizeTaxProposal(ClosedSerializer):
    enabled = serializers.BooleanField()
    rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    threshold = serializers.DecimalField(max_digits=12, decimal_places=2)


class PrizeShareRow(ClosedSerializer):
    id = serializers.IntegerField()
    member_id = serializers.IntegerField(allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    state = serializers.CharField()
    paid = serializers.BooleanField()


class PrizePayableAwardRead(ClosedSerializer):
    id = serializers.IntegerField()
    prize_name = serializers.CharField()
    rank = serializers.IntegerField()
    title = serializers.CharField()
    amount_per_winner = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    paid = serializers.BooleanField()
    kind = serializers.CharField()
    funding = serializers.CharField()
    value_text = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=("owed", "paid", "part_paid", "fulfilled", "sponsor_paid", "forfeited"))
    open_recoveries = serializers.IntegerField()
    tax_proposal = PrizeTaxProposal()
    shares = PrizeShareRow(many=True)


class PrizePayoutPage(ClosedSerializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PayoutRead(many=True)
    awards = PrizePayableAwardRead(many=True)


class OptionsInput(CommandInput):
    results_email = serializers.BooleanField(required=False)
    submission_receipt_email = serializers.BooleanField(required=False)
    finalists_email = serializers.BooleanField(required=False)
    refund_on_disqualification = serializers.BooleanField(required=False)
    refund_on_withdrawal = serializers.BooleanField(required=False)
    refund_if_not_shortlisted = serializers.BooleanField(required=False)
    entry_fee = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
                                         allow_null=True, required=False)
    team_fee = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
                                        allow_null=True, required=False)
    stage_reminder_email = serializers.BooleanField(required=False)  # #178: stage deadline reminders.
    shortlist_email = serializers.BooleanField(required=False)  # #179: shortlisted and not-shortlisted teams.
    entry_fee_stage = serializers.IntegerField(min_value=1, max_value=10, required=False,
                                               help_text="S17: the stage position the entry fee is paid before.")
    show_prize_amounts = serializers.BooleanField(required=False, help_text="G6: prizes on the public page.")
    prize_claim_days = serializers.IntegerField(min_value=1, max_value=365, allow_null=True, required=False,
                                                help_text="G4: days after results in which winners claim.")
    deposit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
                                              allow_null=True, required=False,
                                              help_text="G10: refundable deposit (events.deposits).")
    deposit_requires_submission = serializers.BooleanField(required=False)


class OptionsRead(ResultEnvelope):
    results_email = serializers.BooleanField()
    submission_receipt_email = serializers.BooleanField()
    finalists_email = serializers.BooleanField()
    stage_reminder_email = serializers.BooleanField()
    shortlist_email = serializers.BooleanField()
    entry_fee_stage = serializers.IntegerField()
    refund_on_disqualification = serializers.BooleanField()
    refund_on_withdrawal = serializers.BooleanField()
    refund_if_not_shortlisted = serializers.BooleanField()
    entry_fee = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    team_fee = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    show_prize_amounts = serializers.BooleanField()
    prize_claim_days = serializers.IntegerField(allow_null=True)
    deposit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    deposit_requires_submission = serializers.BooleanField()
    deposits_settled_at = serializers.DateTimeField(allow_null=True)
    currency = serializers.CharField()
    results_email_sent = serializers.BooleanField()
    published_result_version = serializers.IntegerField(allow_null=True, help_text="Send-now's expected_version.")
