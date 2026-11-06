"""Release-2 lane L2 state: integrity-check jobs, storage receipts and mentor chat routes.

* `SubmissionIntegrityCheck` -- one row per submission snapshot, the job state of the
  informational GitHub first-commit check (#8). The flag itself stays in
  `SubmissionIntegrityFlag`; a check never changes a submission's state or eligibility.
* `SubmissionStorageCleanupReceipt` -- durable, FK-free proof that cleanup removed every
  object version, delete marker and multipart upload of one asset key. It keeps a key
  HASH only (no bucket locator), so it is evidence, never a delete capability.
* `MentorAlertRoute` -- which of the space's chat rooms receive this event's new Mentor
  Desk help alerts. Rooms get a short outbound notice only; no buttons, no names.
"""

from django.utils.translation import gettext, gettext_lazy
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SubmissionIntegrityCheck(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        CLEAR = "clear", gettext_lazy("No early commits")
        FLAGGED = "flagged", gettext_lazy("Flagged for information")
        NO_REPOSITORY = "no_repository", gettext_lazy("No GitHub repository")
        UNAVAILABLE = "unavailable", gettext_lazy("GitHub unavailable")

    snapshot = models.OneToOneField("events.SubmissionSnapshot", on_delete=models.CASCADE,
                                    related_name="integrity_check")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    checked_at = models.DateTimeField(null=True, blank=True)
    # #180 S14: the stage-deadline push signal, checked once after the stage closes ("" until then).
    after_deadline_state = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        app_label = "events"
        indexes = [models.Index(fields=["state", "next_attempt_at"], name="ev_integrity_check_due")]


class SubmissionStorageCleanupReceipt(models.Model):
    """Append-only; survives event and tenant deletion (no foreign keys)."""

    makerspace_id_snapshot = models.PositiveBigIntegerField()
    event_id_snapshot = models.PositiveBigIntegerField()
    asset_uuid = models.UUIDField()
    key_sha256 = models.CharField(max_length=64)
    versions_deleted = models.PositiveIntegerField(default=0)
    markers_deleted = models.PositiveIntegerField(default=0)
    uploads_aborted = models.PositiveIntegerField(default=0)
    verified_absent_at = models.DateTimeField()

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=["asset_uuid", "key_sha256"],
                                               name="ev_storage_receipt_once")]
        indexes = [models.Index(fields=["makerspace_id_snapshot", "event_id_snapshot"],
                                name="ev_storage_receipt_scope")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(gettext("Storage cleanup receipts are append-only."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Storage cleanup receipts are permanent."))


class MentorAlertRoute(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="mentor_alert_routes")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    destination = models.ForeignKey("integrations.NotificationDestination", on_delete=models.CASCADE,
                                    related_name="mentor_alert_routes")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "events"
        constraints = [models.UniqueConstraint(fields=["event", "destination"], name="ev_mentor_alert_route_once")]
