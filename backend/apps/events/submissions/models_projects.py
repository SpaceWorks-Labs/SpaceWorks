from django.utils.translation import gettext
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .pii import PrivateDocumentMixin


class HackathonSubmission(PrivateDocumentMixin, models.Model):
    pii_document_fields = frozenset({"form_answers"})
    pii_text_fields = frozenset({"triage_reason"})
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="submissions")
    team = models.OneToOneField("events.HackathonTeam", on_delete=models.PROTECT, related_name="submission")
    state = models.CharField(max_length=24, default="draft")
    version = models.PositiveIntegerField(default=1)
    links_version = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200, blank=True)
    tagline = models.CharField(max_length=300, blank=True)
    problem = models.TextField(blank=True)
    description = models.TextField(blank=True)
    challenges = models.TextField(blank=True)
    tech_tags = models.JSONField(default=list)
    ai_declaration = models.JSONField(default=dict)
    reuse_declaration = models.JSONField(default=dict)
    form_answers = models.TextField(default="{}")
    track_ids = models.JSONField(default=list)
    prize_ids = models.JSONField(default=list)
    asset_ids = models.JSONField(default=list)
    public_asset_ids = models.JSONField(default=list)
    public_requested = models.BooleanField(default=False)
    current_snapshot = models.ForeignKey("events.SubmissionSnapshot", null=True, on_delete=models.PROTECT, related_name="+")
    triage = models.CharField(max_length=16, default="pending")
    triage_reason = models.TextField(max_length=1000, blank=True)
    submitted_at = models.DateTimeField(null=True)
    locked_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "events"
        constraints = [models.CheckConstraint(condition=models.Q(state__in=["draft", "submitted", "locked",
            "under_review", "judged", "disqualified", "withdrawn"]), name="submission_valid_state"),
            models.CheckConstraint(condition=models.Q(triage__in=["pending", "eligible", "ineligible", "hidden"]),
                                   name="submission_valid_triage")]


class SubmissionSnapshot(PrivateDocumentMixin, models.Model):
    pii_document_fields = frozenset({"project"})
    pii_text_fields = frozenset({"amendment_reason"})
    submission = models.ForeignKey(HackathonSubmission, on_delete=models.CASCADE, related_name="snapshots")
    sequence = models.PositiveIntegerField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(default=timezone.now)
    sealed_member_ids = models.JSONField(default=list)
    project = models.TextField()
    content_sha256 = models.CharField(max_length=64)
    source_content_sha256 = models.CharField(max_length=64, blank=True)
    late = models.BooleanField(default=False)
    amendment_of = models.ForeignKey("self", null=True, on_delete=models.PROTECT, related_name="+")
    amendment_reason = models.TextField(max_length=1000, blank=True)

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=["submission", "sequence"], name="snapshot_sequence_unique")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(gettext("Submission snapshots are immutable."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Submission snapshots are retained."))


class SubmissionLink(models.Model):
    submission = models.ForeignKey(HackathonSubmission, on_delete=models.CASCADE, related_name="links")
    kind = models.CharField(max_length=16)
    url = models.URLField(max_length=2048)
    provider = models.CharField(max_length=32)
    public_requested = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        app_label = "events"


class SnapshotAsset(models.Model):
    snapshot = models.ForeignKey(SubmissionSnapshot, on_delete=models.CASCADE, related_name="asset_refs")
    asset = models.ForeignKey("events.SubmissionAsset", on_delete=models.PROTECT, related_name="snapshot_refs")
    public_requested = models.BooleanField(default=False)

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=["snapshot", "asset"], name="snapshot_asset_unique")]


class SnapshotLink(models.Model):
    snapshot = models.ForeignKey(SubmissionSnapshot, on_delete=models.CASCADE, related_name="link_refs")
    link = models.ForeignKey(SubmissionLink, on_delete=models.PROTECT, related_name="snapshot_refs")
    kind = models.CharField(max_length=16)
    url = models.URLField(max_length=2048)
    provider = models.CharField(max_length=32)
    public_requested = models.BooleanField(default=False)

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=["snapshot", "link"], name="snapshot_link_unique")]


class SnapshotTrack(models.Model):
    snapshot = models.ForeignKey(SubmissionSnapshot, on_delete=models.CASCADE, related_name="track_refs")
    track = models.ForeignKey("events.HackathonTrack", on_delete=models.PROTECT, related_name="+")

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=["snapshot", "track"], name="snapshot_track_unique")]


class SnapshotPrize(models.Model):
    snapshot = models.ForeignKey(SubmissionSnapshot, on_delete=models.CASCADE, related_name="prize_refs")
    prize = models.ForeignKey("events.HackathonPrize", on_delete=models.PROTECT, related_name="+")

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=["snapshot", "prize"], name="snapshot_prize_unique")]


class SubmissionIntegrityFlag(PrivateDocumentMixin, models.Model):
    pii_text_fields = frozenset({"reason"})
    snapshot = models.ForeignKey(SubmissionSnapshot, on_delete=models.CASCADE, related_name="integrity_flags")
    rule_key = models.CharField(max_length=64)
    severity = models.CharField(max_length=16, default="informational", editable=False)
    evidence = models.JSONField(default=dict)
    checked_at = models.DateTimeField(default=timezone.now)
    state = models.CharField(max_length=16, default="open")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    reason = models.TextField(max_length=1000, blank=True)

    class Meta:
        app_label = "events"
        constraints = [models.CheckConstraint(condition=models.Q(severity="informational"),
                                             name="submission_flag_information_only"),
                       models.UniqueConstraint(fields=["snapshot", "rule_key"], name="submission_integrity_rule_unique")]
