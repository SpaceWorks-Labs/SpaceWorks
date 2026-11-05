"""People's choice (#181 S3): an optional extra award voted by signed-in members on the public gallery.

It never touches judging. A missing config row means the award is off for that event (new events
start off). One ballot per person per event, changeable until the window closes; a staff void keeps
the row so the voter cannot simply vote again. Publishing happens once and freezes the standings;
a winning standing is what a prize payout points at, exactly like a judged ``EventAward``.
"""

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .models_base import AppendOnly, EventOwned

AUDIENCES = (("members", "Any signed-in member"), ("attendees", "Checked-in attendees only"))


class PeoplesChoiceConfig(EventOwned):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="peoples_choice")
    enabled = models.BooleanField(default=False)
    audience = models.CharField(max_length=10, default="members", choices=AUDIENCES)
    opens_at = models.DateTimeField(null=True, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    prize = models.ForeignKey("events.HackathonPrize", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    open_email = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(audience__in=("members", "attendees")), name="ev_pc_audience"),
            models.CheckConstraint(condition=Q(opens_at__isnull=True) | Q(closes_at__isnull=True)
                                   | Q(closes_at__gt=F("opens_at")), name="ev_pc_window_order"),
        ]


class PeoplesChoiceVote(models.Model):
    """The voter's one ballot. ``handle`` is the opaque id staff void by; it never orders or dates a vote."""
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.CASCADE, related_name="+")
    handle = models.UUIDField(default=uuid4, editable=False)
    version = models.PositiveIntegerField(default=1)
    cast_at = models.DateTimeField(auto_now_add=True)
    changed_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.ForeignKey("events.JudgingReason", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("event", "voter"), name="ev_pc_one_vote_per_person"),
            models.CheckConstraint(condition=Q(voided_at__isnull=True, void_reason__isnull=True)
                                   | Q(voided_at__isnull=False, void_reason__isnull=False), name="ev_pc_void_shape"),
        ]


class PeoplesChoiceResult(AppendOnly):
    """Publish-once: the frozen count and the prize (if any) the award carries."""
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="peoples_choice_result")
    prize = models.ForeignKey("events.HackathonPrize", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    prize_name = models.CharField(max_length=160)
    total_votes = models.PositiveIntegerField()
    published_at = models.DateTimeField()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")


class PeoplesChoiceStanding(AppendOnly):
    """One counted project at publication. Winners (joint on a tie) are what payouts and badges read."""
    result = models.ForeignKey(PeoplesChoiceResult, on_delete=models.CASCADE, related_name="standings")
    submission_snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    votes = models.PositiveIntegerField()
    rank = models.PositiveSmallIntegerField()
    winner = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("result", "submission_snapshot"), name="ev_pc_standing_once"),
            models.CheckConstraint(condition=Q(rank__gte=1), name="ev_pc_standing_rank"),
            models.CheckConstraint(condition=Q(winner=False) | Q(rank=1), name="ev_pc_winner_rank"),
        ]
