"""Submission stages (#177, #178, #179): per-event windows, content rules and shortlist gates.

Every hackathon event has at least one stage. Migration 0069 turned each existing submission window
into stage 1 ("Single submission"), so existing events behave exactly as before. A stage snapshot is
the project's ordinary frozen ``SubmissionSnapshot``; ``SnapshotStage`` records which stage froze it,
and ``SubmissionStageEntry`` points at the current snapshot of one project for one stage.
"""
from django.conf import settings
from django.db import models
from django.db.models import Deferrable, F, Q

from apps.events.judging.models_base import AppendOnly

CONTENT_MODES = ("files_and_links", "files_only", "links_only", "presentation")
LATE_POLICIES = ("reject", "accept_flagged")
RESUBMISSION = ("until_deadline", "once")
TRIAGE = ("pending", "eligible", "ineligible", "hidden")
MAX_STAGES = 10


class SubmissionStage(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="submission_stages")
    position = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=2000)
    opens_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    grace_minutes = models.PositiveIntegerField(default=0)
    late_policy = models.CharField(max_length=16, default="reject", choices=[(v, v) for v in LATE_POLICIES])
    resubmission = models.CharField(max_length=16, default="until_deadline", choices=[(v, v) for v in RESUBMISSION])
    requires_previous = models.BooleanField(default=False)
    content_mode = models.CharField(max_length=16, default="files_and_links", choices=[(v, v) for v in CONTENT_MODES])
    required_link_kinds = models.JSONField(default=list, blank=True)
    min_files = models.PositiveSmallIntegerField(default=0)
    max_files = models.PositiveSmallIntegerField(null=True, blank=True)
    max_links = models.PositiveSmallIntegerField(null=True, blank=True)
    accepted_families = models.JSONField(default=list, blank=True)
    max_bytes_per_file = models.PositiveBigIntegerField(null=True, blank=True)
    video_hosts = models.JSONField(default=list, blank=True)
    custom_fields = models.JSONField(default=list, blank=True)
    shortlist_after = models.BooleanField(default=False)
    shortlist_label = models.CharField(max_length=60, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "events"
        ordering = ("event", "position")
        constraints = [
            models.UniqueConstraint(fields=("event", "position"), name="ev_stage_position",
                                    deferrable=Deferrable.DEFERRED),
            models.CheckConstraint(condition=Q(content_mode__in=CONTENT_MODES), name="ev_stage_content_mode"),
            models.CheckConstraint(condition=Q(position__gte=1, position__lte=MAX_STAGES), name="ev_stage_position_range"),
            models.CheckConstraint(condition=Q(grace_minutes__lte=1440), name="ev_stage_grace"),
            models.CheckConstraint(condition=Q(late_policy__in=LATE_POLICIES), name="ev_stage_late_policy"),
            models.CheckConstraint(condition=Q(resubmission__in=RESUBMISSION), name="ev_stage_resubmission"),
            models.CheckConstraint(condition=Q(max_bytes_per_file__isnull=True) | Q(max_bytes_per_file__gte=1),
                                   name="ev_stage_file_bytes"),
            models.CheckConstraint(condition=Q(min_files__lte=100), name="ev_stage_min_files"),
            models.CheckConstraint(condition=Q(max_files__isnull=True) | Q(max_files__gte=1, max_files__lte=100),
                                   name="ev_stage_max_files"),
            models.CheckConstraint(condition=Q(max_links__isnull=True) | Q(max_links__gte=1, max_links__lte=30),
                                   name="ev_stage_max_links"),
            models.CheckConstraint(condition=Q(max_files__isnull=True) | Q(max_files__gte=F("min_files")),
                                   name="ev_stage_file_range"),
            models.CheckConstraint(condition=~Q(content_mode__in=("links_only", "presentation")) | Q(min_files=0),
                                   name="ev_stage_optional_files"),
            models.CheckConstraint(condition=~Q(content_mode="presentation") | Q(required_link_kinds=[]),
                                   name="ev_stage_presentation_links"),
            models.CheckConstraint(condition=~Q(content_mode="links_only") | Q(max_files__isnull=True),
                                   name="ev_stage_links_only_files"),
            models.CheckConstraint(condition=~Q(content_mode="files_only") | Q(max_links__isnull=True, required_link_kinds=[]),
                                   name="ev_stage_files_only_links"),
            models.CheckConstraint(condition=Q(opens_at__isnull=True) | Q(deadline__isnull=True) | Q(deadline__gt=F("opens_at")),
                                   name="ev_stage_window"),
        ]


class SubmissionStageEntry(models.Model):
    """One project's place in one stage: its current frozen snapshot for that stage."""
    submission = models.ForeignKey("events.HackathonSubmission", on_delete=models.CASCADE, related_name="stage_entries")
    stage = models.ForeignKey(SubmissionStage, on_delete=models.PROTECT, related_name="entries")
    current_snapshot = models.ForeignKey("events.SubmissionSnapshot", null=True, blank=True,
                                         on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(null=True, blank=True)
    # S5: triage belongs to the stage submission; a re-submission resets it to pending. The private
    # reason stays on the project (encrypted) and in the audit log.
    triage = models.CharField(max_length=16, default="pending", choices=[(v, v) for v in TRIAGE])
    version = models.PositiveIntegerField(default=1)

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=("submission", "stage"), name="ev_stage_entry_once"),
                       models.CheckConstraint(condition=Q(triage__in=TRIAGE), name="ev_stage_entry_triage")]


class StageExtension(AppendOnly):
    """S2: a per-team deadline extension. The team's effective deadline is the later of the two."""
    stage = models.ForeignKey(SubmissionStage, on_delete=models.PROTECT, related_name="extensions")
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.PROTECT, related_name="+")
    until = models.DateTimeField()
    reason = models.TextField(max_length=1000)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "events"


class SnapshotStage(AppendOnly):
    """Which stage froze a snapshot. Written once, with the snapshot."""
    snapshot = models.OneToOneField("events.SubmissionSnapshot", on_delete=models.CASCADE, related_name="stage_ref")
    stage = models.ForeignKey(SubmissionStage, on_delete=models.PROTECT, related_name="+")
    extension = models.ForeignKey(StageExtension, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        app_label = "events"


class StageShortlist(AppendOnly):
    """One applied shortlist selection for a stage. The newest one is the stage's current shortlist."""
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    stage = models.ForeignKey(SubmissionStage, on_delete=models.PROTECT, related_name="shortlists")
    source_round = models.ForeignKey("events.JudgingRound", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    selection = models.CharField(max_length=8, choices=(("top_n", "Top N"), ("manual", "Hand-picked")))
    top_n = models.PositiveSmallIntegerField(null=True, blank=True)
    fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "events"
        constraints = [
            models.CheckConstraint(condition=Q(selection__in=("top_n", "manual")), name="ev_shortlist_selection"),
            models.CheckConstraint(condition=Q(selection="manual") | Q(top_n__gte=1, source_round__isnull=False),
                                   name="ev_shortlist_top_n"),
        ]


class StageShortlistEntry(AppendOnly):
    shortlist = models.ForeignKey(StageShortlist, on_delete=models.CASCADE, related_name="entries")
    submission = models.ForeignKey("events.HackathonSubmission", on_delete=models.PROTECT, related_name="+")
    snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    source_rank = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=("shortlist", "submission"), name="ev_shortlist_entry_once")]


class StageShortlistAnnouncement(AppendOnly):
    """Publishing a stage shortlist happens once; it is what opens the next stage to the chosen teams."""
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    shortlist = models.OneToOneField(StageShortlist, on_delete=models.PROTECT, related_name="announcement")
    published_at = models.DateTimeField()
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        app_label = "events"
