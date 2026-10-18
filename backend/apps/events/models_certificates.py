from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin
from apps.events.models_feedback import EventFeedbackResponse
from apps.events.models_registration import EventRegistration


class EventAttendanceCertificate(ScopedPiiModelMixin, models.Model):
    class Kind(models.TextChoices):
        ATTENDANCE = "attendance", "Attendance"
        PARTICIPANT = "participant", "Participant"
        FINALIST = "finalist", "Finalist"
        WINNER = "winner", "Winner"
        VOLUNTEER_THANKS = "volunteer_thanks", "Volunteer thanks"
        MENTOR_THANKS = "mentor_thanks", "Mentor thanks"
        JUDGE_THANKS = "judge_thanks", "Judge thanks"

    event = models.ForeignKey("events.Event", on_delete=models.PROTECT, related_name="certificates")
    recipient_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True, related_name="event_certificates")
    role_assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT,
                                       null=True, blank=True, related_name="certificates")
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.ATTENDANCE)
    award = models.ForeignKey("events.HackathonPrize", on_delete=models.PROTECT,
                             null=True, blank=True, related_name="certificates")
    result_revision = models.ForeignKey("events.EventResultRevision", on_delete=models.PROTECT,
                                       null=True, blank=True, related_name="certificates")
    public_verification_enabled = models.BooleanField(default=False)
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RENDERING = "rendering", "Rendering"
        ACTIVE = "active", "Active"
        FAILED = "failed", "Failed"
        REVOKED = "revoked", "Revoked"

    class RevocationReason(models.TextChoices):
        ATTENDANCE_CORRECTED = "attendance_corrected", "Attendance corrected"
        EVENT_CANCELLED = "event_cancelled", "Event cancelled"
        STAFF_REVOKED = "staff_revoked", "Staff revoked"

    response = models.ForeignKey(
        EventFeedbackResponse,
        on_delete=models.PROTECT,
        related_name="certificates",
        null=True, blank=True,
    )
    registration = models.ForeignKey(
        EventRegistration,
        on_delete=models.PROTECT,
        related_name="attendance_certificates",
        null=True, blank=True,
    )
    serial = models.UUIDField(default=uuid4, unique=True, editable=False)
    revision = models.PositiveIntegerField()
    template_revision = models.ForeignKey(
        "events.EventCertificateTemplateRevision", on_delete=models.PROTECT,
        null=True, blank=True, related_name="certificates",
    )
    layout_snapshot = models.JSONField(default=dict, blank=True)
    recipient_name = models.TextField()
    event_title = models.CharField(max_length=200)
    event_starts_at = models.DateTimeField()
    event_ends_at = models.DateTimeField()
    event_timezone_name = models.CharField(max_length=64, default="UTC")
    issuer_name = models.CharField(max_length=200)
    object_key = models.CharField(max_length=512, unique=True)
    content_type = models.CharField(max_length=64, default="application/pdf")
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    rendered_at = models.DateTimeField(null=True, blank=True)
    render_token = models.UUIDField(null=True, blank=True, editable=False)
    render_started_at = models.DateTimeField(null=True, blank=True, editable=False)
    render_attempts = models.PositiveIntegerField(default=0, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    revocation_reason = models.CharField(
        max_length=32,
        choices=RevocationReason.choices,
        blank=True,
    )

    class Meta:
        ordering = ["event_id", "id"]
        constraints = [
            models.CheckConstraint(condition=(
                Q(registration__isnull=False, role_assignment__isnull=True)
                | Q(registration__isnull=True, role_assignment__isnull=False, response__isnull=True)
            ), name="event_certificate_exact_subject"),
            models.UniqueConstraint(
                fields=["registration", "kind", "award", "revision"],
                condition=Q(registration__isnull=False), nulls_distinct=False,
                name="event_cert_reg_revision_v2",
            ),
            models.UniqueConstraint(
                fields=["role_assignment", "kind", "award", "revision"],
                condition=Q(role_assignment__isnull=False), nulls_distinct=False,
                name="event_cert_role_revision_v2",
            ),
            models.UniqueConstraint(
                fields=["registration", "kind", "award"],
                condition=Q(registration__isnull=False) & ~Q(status="revoked"), nulls_distinct=False,
                name="event_cert_reg_live_v2",
            ),
            models.UniqueConstraint(
                fields=["role_assignment", "kind", "award"],
                condition=Q(role_assignment__isnull=False) & ~Q(status="revoked"), nulls_distinct=False,
                name="event_cert_role_live_v2",
            ),
        ]

    def clean(self):
        super().clean()
        if self.response_id and self.registration_id:
            if self.response.registration_id != self.registration_id:
                raise ValidationError(
                    {"response": "Response and certificate registration must match."}
                )
        if self.content_type != "application/pdf":
            raise ValidationError({"content_type": "Certificates must be PDF files."})
        if bool(self.registration_id) == bool(self.role_assignment_id):
            raise ValidationError("A certificate has exactly one registration or role subject.")
        subject = self.registration if self.registration_id else self.role_assignment
        if subject.event_id != self.event_id or subject.member_id != self.recipient_member_id:
            raise ValidationError("Certificate event and recipient must match its subject.")
        if self.award_id and self.award.event_id != self.event_id:
            raise ValidationError("Award belongs to another event.")
        if self.result_revision_id and self.result_revision.event_id != self.event_id:
            raise ValidationError("Results belong to another event.")
        if self.template_revision_id and self.template_revision.event_id != self.event_id:
            raise ValidationError({"template_revision": "Template belongs to another event."})

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            issuance_fields = (
                "response_id", "registration_id", "serial", "revision",
                "recipient_name", "event_title", "event_starts_at",
                "event_ends_at", "issuer_name", "object_key", "content_type",
                "issued_at", "template_revision_id", "layout_snapshot",
                "event_id", "recipient_member_id", "role_assignment_id", "kind", "award_id", "result_revision_id",
                "event_timezone_name",
            )
            if any(
                getattr(self, field) != getattr(original, field)
                for field in issuance_fields
            ):
                raise ValidationError("Certificate issuance snapshots are immutable.")
            allowed = {
                self.Status.PENDING: {self.Status.RENDERING},
                self.Status.FAILED: {self.Status.RENDERING},
                self.Status.RENDERING: {self.Status.ACTIVE, self.Status.FAILED},
                self.Status.ACTIVE: {self.Status.REVOKED},
                self.Status.REVOKED: set(),
            }
            if self.status != original.status and self.status not in allowed[original.status]:
                raise ValidationError({"status": "Invalid certificate transition."})
            if original.status == self.Status.ACTIVE:
                frozen = ("size_bytes", "sha256", "rendered_at")
                if any(getattr(self, field) != getattr(original, field) for field in frozen):
                    raise ValidationError("An active certificate artifact is immutable.")
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)
