"""Canonical owner-bound support request, independent of admission decisions."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Versioned


class GrantRequest(ScopedPiiModelMixin, Versioned):
    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    programme = models.ForeignKey("event_reimbursements.ReimbursementProgramme", on_delete=models.CASCADE,
                                 related_name="requests")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="grant_requests")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="grant_requests")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, null=True, related_name="+")
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.CASCADE, null=True, related_name="+")
    creation_operation_id = models.UUIDField(null=True)
    request_phase = models.CharField(max_length=16, choices=[(v, v) for v in ("application", "after_acceptance")])
    #: Lane L21a: `crew` is an organising-crew expense claim (behind `events.crew_claims`).
    #: Parity C17: `staff` is a claim staff filed for themselves or for someone else (behind `events.staff_claims`).
    #: Who filed it is in the append-only audit row `event.reimbursement.staff_claim_filed`, not a column.
    kind = models.CharField(max_length=12, default="participant",
                            choices=[(v, v) for v in ("participant", "crew", "staff")])
    state = models.CharField(max_length=12, default="draft", choices=[(v, v) for v in (
        "draft", "requested", "waitlisted", "awarded", "declined", "withdrawn", "expired")])
    origin = models.TextField(blank=True)
    destination = models.TextField(blank=True)
    mode = models.CharField(max_length=8)
    need_statement = models.TextField(blank=True)
    itinerary = models.TextField(default="{}")
    estimated_cost = models.TextField(default="{}")
    distance_km = models.DecimalField(max_digits=8, decimal_places=3, null=True)
    distance_verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                             null=True, related_name="+")
    category_estimates = models.JSONField(default=list)
    estimated_total_minor = models.PositiveBigIntegerField(default=0)
    currency = models.CharField(max_length=3)
    submitted_at = models.DateTimeField(null=True)
    reviewed_at = models.DateTimeField(null=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    reason_code = models.CharField(max_length=64, blank=True)
    reason = models.TextField(blank=True)
    eligibility_snapshot = models.TextField(default="{}")
    eligibility_version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("programme", "member"), name="reimb_request_unique_owner"),
            models.CheckConstraint(condition=(models.Q(state="draft") | models.Q(registration__isnull=False)
                | models.Q(application__isnull=False)), name="reimb_request_canonical_subject"),
            models.CheckConstraint(condition=(models.Q(distance_km__isnull=True)
                | models.Q(distance_km__gte=0, distance_km__lte=40075)), name="reimb_request_distance"),
        ]
