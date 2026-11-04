"""Programme policy is distinct from finite pool accounting."""

from django.conf import settings
from django.db import models
from .model_base import Versioned


def categories():
    return ["rail", "air", "bus", "ground_transport", "lodging"]


def exclusions():
    return ["meals", "visa", "insurance", "baggage", "upgrades", "fees"]


class ReimbursementProgramme(Versioned):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="reimbursement_programme")
    enabled = models.BooleanField(default=False)
    imported_paused = models.BooleanField(default=False)
    currency = models.CharField(max_length=3)
    request_phase = models.CharField(max_length=16, default="both", choices=[(v, v) for v in (
        "application", "after_acceptance", "both")])
    request_opens_at = models.DateTimeField(null=True)
    request_closes_at = models.DateTimeField(null=True)
    award_mode = models.CharField(max_length=16, default="need_based", choices=[(v, v) for v in (
        "fixed_tier", "route_cap", "percentage", "need_based")])
    tier_rules = models.JSONField(default=dict)
    allowed_categories = models.JSONField(default=categories)
    exclusions = models.JSONField(default=exclusions)
    min_distance_km = models.DecimalField(max_digits=8, decimal_places=3, null=True)
    eligible_countries = models.JSONField(default=list)
    eligible_cohorts = models.JSONField(default=list)
    #: Lane L21a: a request is allowed once the application reaches this review stage and stands.
    min_application_stage = models.PositiveSmallIntegerField(null=True, blank=True)
    award_accept_days = models.PositiveSmallIntegerField(default=4)
    claim_due_at = models.DateTimeField()
    attendance_required = models.BooleanField(default=True)
    require_project_submission = models.BooleanField(default=False)
    permitted_venue_sources = models.JSONField(default=list)
    category_limits = models.JSONField(default=dict)
    finance_policy_revision = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    initialization_operation_id = models.UUIDField(unique=True, editable=False)
    initialization_digest = models.CharField(max_length=64, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(version__gte=1), name="reimb_programme_version_positive"),
            models.CheckConstraint(condition=(models.Q(min_distance_km__isnull=True)
                | models.Q(min_distance_km__gte=0, min_distance_km__lte=40075)), name="reimb_distance_bounds"),
            models.CheckConstraint(condition=(models.Q(request_opens_at__isnull=True)
                | models.Q(request_closes_at__isnull=True)
                | models.Q(request_closes_at__gt=models.F("request_opens_at"))), name="reimb_request_window"),
        ]
