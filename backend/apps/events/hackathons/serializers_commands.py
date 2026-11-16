"""Closed action-specific payloads. No generic client action dispatcher."""
from django.utils.translation import gettext
from rest_framework import serializers
from .admission_inputs import CommandInput, LiteralBoolean, StrictSerializer


class RsvpInput(CommandInput):
    decision = serializers.ChoiceField(choices=["accept", "decline", "waitlist"])


class WithdrawalInput(CommandInput):
    reason_code = serializers.ChoiceField(choices=["participant_withdrew", "cannot_attend", "team_disbanded"])


class DateReviewInput(CommandInput):
    event_date_revision = serializers.IntegerField(min_value=1)
    as_of_date = serializers.DateField()
    confirmed = LiteralBoolean()


class StaffRsvpInput(RsvpInput):
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{2,39}$")


class ExtendRsvpInput(CommandInput):
    rsvp_due_at = serializers.DateTimeField()
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{2,39}$")


class DecisionSubjectInput(StrictSerializer):
    application_id = serializers.IntegerField(min_value=1, required=False)
    cohort_id = serializers.IntegerField(min_value=1, required=False)
    expected_version = serializers.IntegerField(min_value=1)
    outcome = serializers.ChoiceField(choices=["offer", "waitlist", "reject", "advance"])
    reason_code = serializers.RegexField(r"^[a-z][a-z0-9_]{2,39}$")
    review_override_code = serializers.RegexField(r"^[a-z][a-z0-9_]{2,39}$", required=False)
    #: Lane L21a: the stage an `advance` moves the application on from.
    stage_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if ("application_id" in attrs) == ("cohort_id" in attrs):
            raise serializers.ValidationError(gettext("Choose exactly one subject."))
        if attrs["outcome"] == "advance" and "stage_id" not in attrs:
            raise serializers.ValidationError(gettext("Name the stage the application advances from."))
        return attrs


class StageInput(CommandInput):
    decisions = DecisionSubjectInput(many=True, min_length=1, max_length=200)


class BatchInput(CommandInput):
    batch_id = serializers.IntegerField(min_value=1)


class ReviewAssignInput(CommandInput):
    subjects = serializers.ListField(child=serializers.DictField(), min_length=1, max_length=200)
    reviewer_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=200)


class ReviewInput(CommandInput):
    scores = serializers.DictField(child=serializers.IntegerField(min_value=1, max_value=5), required=False)
    notes = serializers.CharField(max_length=5000, allow_blank=True, required=False, default="")
    recusal_code = serializers.ChoiceField(choices=["self", "team", "affiliation", "declared"], required=False)

    def validate(self, attrs):
        if ("scores" in attrs) == ("recusal_code" in attrs):
            raise serializers.ValidationError(gettext("Submit scores or recuse."))
        return attrs


class TeamInput(CommandInput):
    name = serializers.CharField(max_length=100, required=False)
    seeking_members = LiteralBoolean(required=False)
    finder_intro = serializers.CharField(max_length=500, allow_blank=True, required=False)
    skills = serializers.ListField(child=serializers.CharField(max_length=40), max_length=20, required=False)


class InviteInput(CommandInput):
    email = serializers.EmailField(max_length=254, allow_blank=True, required=False, default="", write_only=True)
    rotate = LiteralBoolean(required=False, default=False)
    revoke_only = LiteralBoolean(required=False, default=False)


class AcceptInput(CommandInput):
    request_id = serializers.IntegerField(min_value=1, required=False)
    token = serializers.CharField(min_length=32, max_length=128, required=False, write_only=True)

    def validate(self, attrs):
        if ("request_id" in attrs) == ("token" in attrs):
            raise serializers.ValidationError(gettext("Choose a request or invitation."))
        return attrs


class DeclineRequestInput(CommandInput):
    request_id = serializers.IntegerField(min_value=1)


class CommentInput(CommandInput):
    body = serializers.CharField(max_length=2000, trim_whitespace=True)


class FinderInput(CommandInput):
    opted_in = LiteralBoolean(required=False)
    intro = serializers.CharField(max_length=500, allow_blank=True, required=False)
    skills = serializers.ListField(child=serializers.CharField(max_length=40), max_length=20, required=False)


class LeaveInput(CommandInput):
    #: Also withdraw the leaver's application and registration (E-B3); needs `events.team_moderation`.
    cancel_registration = LiteralBoolean(required=False, default=False)


class HandoverInput(CommandInput):
    new_leader_id = serializers.IntegerField(min_value=1)


class RemoveMemberInput(CommandInput):
    member_id = serializers.IntegerField(min_value=1)


class TeamRenameInput(CommandInput):
    name = serializers.CharField(max_length=100)


class TeamMoveInput(CommandInput):
    member_id = serializers.IntegerField(min_value=1)
    to_team_id = serializers.IntegerField(min_value=1)
