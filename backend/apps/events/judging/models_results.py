"""Immutable finalized result evidence and separate append-only announcements."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from .models_base import AppendOnly, EventOwned


class EventResultRevision(AppendOnly):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="result_revisions")
    version = models.PositiveIntegerField()
    algorithm_version = models.CharField(max_length=40)
    aggregates = models.JSONField()
    content_sha256 = models.CharField(max_length=64)
    source_content_sha256 = models.CharField(max_length=64, blank=True, default="", editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    finalized_at = models.DateTimeField()
    correction_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reason = models.ForeignKey("events.JudgingReason", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("event", "version"), name="ev_result_revision")]


class EventResultRound(AppendOnly):
    result = models.ForeignKey(EventResultRevision, on_delete=models.CASCADE, related_name="rounds")
    round = models.ForeignKey("events.JudgingRound", on_delete=models.PROTECT, related_name="+")
    configuration = models.JSONField()
    calculation = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("result", "round"), name="ev_result_round")]


class EventAward(AppendOnly):
    result = models.ForeignKey(EventResultRevision, on_delete=models.CASCADE, related_name="awards")
    prize = models.ForeignKey("events.HackathonPrize", on_delete=models.PROTECT, related_name="+")
    prize_name = models.CharField(max_length=160)
    submission_snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    rank = models.PositiveSmallIntegerField()
    public_requested = models.BooleanField(default=False)
    reason = models.ForeignKey("events.JudgingReason", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("result", "prize", "rank"), name="ev_award_rank"),
            models.UniqueConstraint(fields=("result", "prize", "submission_snapshot"), name="ev_award_project"),
            models.CheckConstraint(condition=Q(rank__gte=1), name="ev_award_rank_positive"),
        ]


class ResultAnnouncement(AppendOnly):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="result_announcements")
    result = models.OneToOneField(EventResultRevision, on_delete=models.PROTECT, related_name="announcement")
    published_at = models.DateTimeField()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")


class ResultPublicationState(EventOwned):
    """Operational public pointer resets on tenant import; announced history does not."""
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="result_publication")
    current_announcement = models.OneToOneField(ResultAnnouncement, null=True, blank=True,
                                               on_delete=models.PROTECT, related_name="+")


class SponsorWinnerProposal(AppendOnly):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    prize = models.ForeignKey("events.HackathonPrize", on_delete=models.PROTECT, related_name="+")
    submission_snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class JudgingNotice(AppendOnly):
    """Transactional intent. F/G installs a source-backed, deduplicated delivery adapter."""
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=32)
    source_id = models.PositiveBigIntegerField()
    revision = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("event", "kind", "source_id", "revision"), name="ev_judging_notice")]
