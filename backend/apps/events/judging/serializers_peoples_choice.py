"""People's choice (#181 S3) inputs and closed read shapes.

Public and member reads never carry a per-project count before publication; the staff
standings preview is the only pre-publication tally and needs manage_hackathon.
"""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.accounts.pii_presentation import is_platform_superadmin, mask_data, pii_visible
from .serializers import ClosedSerializer, CommandInput
from .serializers_l21b import PayoutInput, PrizeTaxProposal

AUDIENCES = (("members", "Any signed-in member"), ("attendees", "Checked-in attendees only"))
STATES = ("off", "scheduled", "open", "closed", "published")
REFUSALS = ("off", "not_open", "closed", "published", "attendees_only", "voided")


class PeoplesChoiceConfigInput(CommandInput):
    enabled = serializers.BooleanField(required=False)
    audience = serializers.ChoiceField(choices=AUDIENCES, required=False)
    opens_at = serializers.DateTimeField(allow_null=True, required=False)
    closes_at = serializers.DateTimeField(allow_null=True, required=False)
    prize_id = serializers.IntegerField(min_value=1, allow_null=True, required=False,
                                        help_text="An optional prize of this event the award carries.")
    open_email = serializers.BooleanField(required=False,
                                          help_text="Email the event's registrants when voting is switched on (off by default).")


class PeoplesChoiceVoteInput(CommandInput):
    entry_public_id = serializers.UUIDField(help_text="The public gallery project to vote for.")


class PeoplesChoiceVoidInput(CommandInput):
    reason = serializers.CharField(max_length=300)


class PeoplesChoicePayoutInput(PayoutInput):
    award_id = None
    standing_id = serializers.IntegerField(min_value=1, help_text="A winning People's choice standing.")


class PeoplesChoiceConfigRead(ClosedSerializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    enabled = serializers.BooleanField()
    audience = serializers.ChoiceField(choices=AUDIENCES)
    opens_at = serializers.DateTimeField(allow_null=True)
    closes_at = serializers.DateTimeField(allow_null=True)
    prize_id = serializers.IntegerField(allow_null=True)
    prize_name = serializers.CharField(allow_null=True)
    open_email = serializers.BooleanField()
    state = serializers.ChoiceField(choices=STATES)
    ballots = serializers.IntegerField(help_text="Ballots cast and not voided; never a per-project count.")
    allowed_actions = serializers.ListField(child=serializers.CharField())


class PeoplesChoiceStandingRead(ClosedSerializer):
    id = serializers.IntegerField(allow_null=True, help_text="Null in the live preview.")
    snapshot_id = serializers.IntegerField()
    title = serializers.CharField()
    votes = serializers.IntegerField()
    rank = serializers.IntegerField()
    winner = serializers.BooleanField()


class PeoplesChoiceStandingsRead(ClosedSerializer):
    published = serializers.BooleanField()
    published_at = serializers.DateTimeField(allow_null=True)
    prize_name = serializers.CharField()
    total_votes = serializers.IntegerField()
    standings = PeoplesChoiceStandingRead(many=True)


class PeoplesChoiceVoteRowRead(ClosedSerializer):
    """A ballot as staff see it: who voted, never which project they chose.

    The voter's name is masked for a platform superadmin without an open PII window on the space
    (#111 Q12), exactly as ``PiiMaskingSerializerMixin`` masks a model row.
    """
    handle = serializers.UUIDField()
    voter_name = serializers.CharField()
    attended = serializers.BooleanField()
    changed = serializers.BooleanField()
    voided = serializers.BooleanField()
    void_reason = serializers.CharField(allow_null=True)
    version = serializers.IntegerField()
    allowed_actions = serializers.ListField(child=serializers.CharField())
    pii_masked = serializers.BooleanField(required=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        viewer = getattr(self.context.get("request"), "user", None)
        if is_platform_superadmin(viewer) and not pii_visible(viewer, self.context.get("makerspace_id")):
            if mask_data(data, ("voter_name", "void_reason")):
                data["pii_masked"] = True
        return data


class PeoplesChoiceBallotRead(ClosedSerializer):
    event_id = serializers.IntegerField()
    state = serializers.ChoiceField(choices=STATES)
    audience = serializers.ChoiceField(choices=AUDIENCES)
    opens_at = serializers.DateTimeField(allow_null=True)
    closes_at = serializers.DateTimeField(allow_null=True)
    can_vote = serializers.BooleanField()
    refusal = serializers.ChoiceField(choices=REFUSALS, allow_null=True)
    entry_public_id = serializers.UUIDField(allow_null=True, help_text="The project this ballot is for, if any.")
    own_entry_public_ids = serializers.ListField(child=serializers.UUIDField(),
                                                 help_text="Your own team's gallery projects, which you cannot vote for.")
    version = serializers.IntegerField(help_text="Send as expected_version; 0 before the first vote.")


class PeoplesChoiceWinnerRead(ClosedSerializer):
    title = serializers.CharField()
    entry_public_id = serializers.UUIDField(allow_null=True)
    votes = serializers.IntegerField()


class PeoplesChoiceAwardRead(ClosedSerializer):
    prize_name = serializers.CharField()
    total_votes = serializers.IntegerField()
    published_at = serializers.DateTimeField()
    winners = PeoplesChoiceWinnerRead(many=True)


class PeoplesChoicePublicRead(ClosedSerializer):
    event_id = serializers.IntegerField()
    state = serializers.ChoiceField(choices=STATES)
    audience = serializers.ChoiceField(choices=AUDIENCES)
    opens_at = serializers.DateTimeField(allow_null=True)
    closes_at = serializers.DateTimeField(allow_null=True)
    award = PeoplesChoiceAwardRead(allow_null=True, help_text="Only after staff publish; there are no counts before then.")


class PeoplesChoicePayableWinnerRead(ClosedSerializer):
    id = serializers.IntegerField()
    prize_name = serializers.CharField()
    title = serializers.CharField()
    amount_per_winner = MoneyField(max_digits=13, decimal_places=3, allow_null=True)
    paid = serializers.BooleanField()
    tax_proposal = PrizeTaxProposal(help_text="The space's prize-tax proposal (#181 G7, record only).")


class PeoplesChoicePayableWinnersRead(ClosedSerializer):
    winners = PeoplesChoicePayableWinnerRead(many=True)
