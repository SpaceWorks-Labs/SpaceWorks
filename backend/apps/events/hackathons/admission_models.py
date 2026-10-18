"""Admission identities; registration status belongs to its existing service."""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from apps.encryption.mappers import ScopedPiiModelMixin


class HackathonConfig(models.Model):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="hackathon_config")
    enabled = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    review_mode = models.CharField(max_length=8, default="rolling", choices=[(v, v) for v in ("auto", "rolling", "batch")])
    application_opens_at = models.DateTimeField(null=True, blank=True)
    application_closes_at = models.DateTimeField(null=True, blank=True)
    application_form = models.JSONField(default=list)
    team_mode = models.CharField(max_length=24, default="individual_then_team", choices=[(v, v) for v in ("solo", "individual_then_team", "team_together")])
    finder_enabled = models.BooleanField(default=False)
    team_min = models.PositiveSmallIntegerField(default=1)
    team_max = models.PositiveSmallIntegerField(default=4)
    team_lock_at = models.DateTimeField(null=True, blank=True)
    team_eligibility = models.CharField(max_length=12, default="confirmed", choices=[("confirmed", "Confirmed"), ("offered", "Offered")])
    review_count = models.PositiveSmallIntegerField(default=2)
    blind_review = models.BooleanField(default=False)
    review_rubric = models.JSONField(default=dict)
    review_round = models.PositiveIntegerField(default=1)
    review_round_closed = models.BooleanField(default=False)
    rsvp_days = models.PositiveSmallIntegerField(default=4)
    offer_capacity = models.PositiveIntegerField(null=True, blank=True)
    submission_opens_at = models.DateTimeField(null=True, blank=True)
    submission_deadline = models.DateTimeField(null=True, blank=True)
    submission_grace_minutes = models.PositiveIntegerField(default=0)
    late_policy = models.CharField(max_length=16, default="reject", choices=[("reject", "Reject"), ("accept_flagged", "Accept flagged")])
    attendance_required = models.BooleanField(default=True)
    upload_policy = models.CharField(max_length=64, default="hackathon-maker-v1")
    upload_policy_version = models.PositiveIntegerField(default=1)
    storage_budget_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    coc_revision = models.PositiveIntegerField(default=1)
    optional_mlh_schema = models.JSONField(default=dict, blank=True)
    gallery_publication = models.ForeignKey("events.GalleryPublication", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    results_revision = models.ForeignKey("events.EventResultRevision", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    first_results_published_at = models.DateTimeField(null=True, blank=True, editable=False)
    retention_anchor_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(team_min__gte=1, team_max__gte=F("team_min"), team_max__lte=100), name="ha_team_size_bounds"),
            models.CheckConstraint(condition=Q(review_count__gte=1, review_count__lte=20, rsvp_days__gte=1, rsvp_days__lte=30), name="ha_review_rsvp_bounds"),
            models.CheckConstraint(condition=Q(application_opens_at__isnull=True) | Q(application_closes_at__isnull=True) | Q(application_closes_at__gt=F("application_opens_at")), name="ha_application_window"),
            models.CheckConstraint(condition=Q(submission_opens_at__isnull=True) | Q(submission_deadline__isnull=True) | Q(submission_deadline__gt=F("submission_opens_at")), name="ha_submission_window"),
        ]


class HackathonCocRevision(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    revision = models.PositiveIntegerField()
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "revision"], name="ha_coc_revision_unique")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Code of conduct revisions are immutable.")
        return super().save(*args, **kwargs)


class HackathonApplicationCohort(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    team = models.OneToOneField("events.HackathonTeam", on_delete=models.PROTECT, related_name="cohort")
    state = models.CharField(max_length=12, default="draft", choices=[(v, v) for v in ("draft", "submitted", "offered", "waitlisted", "confirmed", "rejected", "declined", "expired", "withdrawn")])
    version = models.PositiveIntegerField(default=1)
    sealed_roster_hash = models.CharField(max_length=64, blank=True)
    sealed_at = models.DateTimeField(null=True, blank=True)


class HackathonApplication(ScopedPiiModelMixin, models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="hackathon_applications")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="hackathon_applications")
    registration = models.OneToOneField("events.EventRegistration", on_delete=models.PROTECT, null=True, blank=True, related_name="hackathon_application")
    cohort = models.ForeignKey(HackathonApplicationCohort, on_delete=models.PROTECT, null=True, blank=True, related_name="applications")
    state = models.CharField(max_length=12, default="draft", choices=[(v, v) for v in ("draft", "submitted", "offered", "waitlisted", "confirmed", "rejected", "declined", "expired", "withdrawn")])
    version = models.PositiveIntegerField(default=1)
    answers_snapshot = models.TextField(default="{}")
    profile_snapshot = models.TextField(default="{}")
    admission_draft = models.TextField(default="{}")
    form_schema_version = models.PositiveSmallIntegerField(default=1)
    form_revision = models.PositiveIntegerField(default=1)
    coc_revision = models.PositiveIntegerField(null=True, blank=True)
    coc_accepted_at = models.DateTimeField(null=True, blank=True)
    optional_consents = models.JSONField(default=dict)
    submitted_at = models.DateTimeField(null=True, blank=True)
    offered_at = models.DateTimeField(null=True, blank=True)
    rsvp_due_at = models.DateTimeField(null=True, blank=True)
    response_at = models.DateTimeField(null=True, blank=True)
    rsvp_accepted_at = models.DateTimeField(null=True, blank=True)
    queue_position_at = models.DateTimeField(null=True, blank=True)
    decision_revision = models.PositiveIntegerField(default=0)
    notified_decision = models.ForeignKey("events.ApplicationDecision", on_delete=models.PROTECT, null=True, blank=True, related_name="notified_applications")
    answers_changed_at = models.DateTimeField(default=timezone.now)
    answer_event_date_revision = models.PositiveIntegerField(null=True, blank=True)
    answer_as_of_date = models.DateField(null=True, blank=True)
    answer_locked_at = models.DateTimeField(null=True, blank=True)
    date_review_required = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "member"], name="ha_event_member_unique"),
            models.CheckConstraint(condition=Q(state="draft") | Q(registration__isnull=False), name="ha_submitted_registration"),
            models.CheckConstraint(condition=Q(coc_revision__isnull=True, coc_accepted_at__isnull=True) | Q(coc_revision__isnull=False, coc_accepted_at__isnull=False), name="ha_coc_evidence_pair"),
        ]
        indexes = [models.Index(fields=["event", "state", "queue_position_at"], name="ha_state_queue_idx")]


class AdmissionWaitlistSweep(models.Model):
    """Omitted coordination cursor; event lock serializes bounded continuation."""
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE)
    last_queue_at = models.DateTimeField(null=True, blank=True)
    last_application_id = models.PositiveBigIntegerField(null=True, blank=True)
    last_cohort_id = models.PositiveBigIntegerField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class HackathonApplicationAnswerRevision(ScopedPiiModelMixin, models.Model):
    application = models.ForeignKey(HackathonApplication, on_delete=models.CASCADE, related_name="answer_revisions")
    sequence = models.PositiveIntegerField()
    answers_snapshot = models.TextField()
    profile_snapshot = models.TextField()
    form_schema_version = models.PositiveSmallIntegerField()
    form_revision = models.PositiveIntegerField()
    coc_revision = models.PositiveIntegerField(null=True, blank=True)
    coc_accepted_at = models.DateTimeField(null=True, blank=True)
    answer_event_date_revision = models.PositiveIntegerField(null=True, blank=True)
    answer_as_of_date = models.DateField(null=True, blank=True)
    locked_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["application", "sequence"], name="ha_answer_revision_unique")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Archived application answers are immutable.")
        return super().save(*args, **kwargs)
