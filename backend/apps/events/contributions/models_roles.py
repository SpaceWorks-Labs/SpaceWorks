from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin
from .models_base import EventBound

ACTIVE = ["draft", "proposed", "applied", "approved"]
ROLES = [(x, x.replace("_", " ")) for x in (
    "co_organizer", "volunteer", "mentor", "judge", "sponsor_rep")]


class EventRolePosting(EventBound):
    role = models.CharField(max_length=16, choices=ROLES[1:3])
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    briefing = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    visibility = models.CharField(max_length=24, default="public", choices=[
        (x, x) for x in ("public", "members", "audience_organizations")])
    approval_required = models.BooleanField(default=True)
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    requirements = models.JSONField(default=dict, blank=True)
    permission_preset = models.JSONField(default=list, blank=True)
    permission_issuer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name="event_role_posting_presets")
    form_schema = models.JSONField(default=dict, blank=True)
    state = models.CharField(max_length=8, default="draft", choices=[
        (x, x) for x in ("draft", "open", "closed")])

    class Meta(EventBound.Meta):
        constraints = [models.CheckConstraint(
            condition=Q(closes_at__gt=models.F("opens_at")), name="event_role_posting_window")]


class EventRoleAssignment(ScopedPiiModelMixin, EventBound):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    posting = models.ForeignKey(EventRolePosting, null=True, blank=True, on_delete=models.PROTECT)
    origin = models.CharField(max_length=8, default="self", choices=[
        (x, x) for x in ("self", "invited", "staff")])
    role = models.CharField(max_length=16, choices=ROLES)
    sponsor = models.ForeignKey("events.EventSponsor", null=True, blank=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=12, default="draft", choices=[
        (x, x) for x in (*ACTIVE, "declined", "withdrawn", "revoked", "completed")])
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="approved_event_roles")
    approved_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    consent_revision = models.PositiveIntegerField(null=True, blank=True)
    application_notes = models.TextField(blank=True)
    answers = models.TextField(default="{}")
    form_schema_version = models.PositiveIntegerField(default=1)
    answer_locked_at = models.DateTimeField(null=True, blank=True)
    date_review_required = models.BooleanField(default=False)
    display_on_page = models.BooleanField(default=False)
    # E resolves this selection, including live per-scope consent; never an avatar URL.
    presentation = models.ForeignKey("events.EventMemberPresentation", null=True, blank=True,
                                     on_delete=models.SET_NULL)
    skills = models.JSONField(default=list, blank=True)
    availability = models.JSONField(default=list, blank=True)
    imported_inert = models.BooleanField(default=False)
    delegated_permissions = models.JSONField(default=list, blank=True)
    track_ids = models.JSONField(default=list, blank=True)

    class Meta(EventBound.Meta):
        constraints = [
            models.UniqueConstraint(fields=["event", "member", "role"],
                condition=Q(state__in=ACTIVE, sponsor__isnull=True), name="event_role_active_null_sponsor"),
            models.UniqueConstraint(fields=["event", "member", "role", "sponsor"],
                condition=Q(state__in=ACTIVE, sponsor__isnull=False), name="event_role_active_sponsor"),
            models.CheckConstraint(condition=(Q(role="sponsor_rep", sponsor__isnull=False)
                | (~Q(role="sponsor_rep") & Q(sponsor__isnull=True))), name="event_role_sponsor_shape"),
        ]


class EventGrantEntitlement(EventBound):
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE)
    series = models.ForeignKey("events.EventSeries", null=True, blank=True, on_delete=models.CASCADE)
    grant = models.ForeignKey("events.EventStaffGrant", on_delete=models.CASCADE,
                              related_name="entitlements")
    source_kind = models.CharField(max_length=8, choices=[(x, x) for x in ("manual", "role", "shift")])
    role_assignment = models.ForeignKey(EventRoleAssignment, null=True, blank=True, on_delete=models.CASCADE)
    shift_signup = models.ForeignKey("events.EventShiftSignup", null=True, blank=True, on_delete=models.CASCADE)
    permissions = models.JSONField(default=list, blank=True)
    track_ids = models.JSONField(default=list, blank=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="event_entitlements_created")
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="event_entitlements_revoked")

    class Meta(EventBound.Meta):
        constraints = [
            models.CheckConstraint(condition=(Q(event__isnull=False, series__isnull=True)
                | Q(event__isnull=True, series__isnull=False, source_kind="manual")),
                name="event_entitlement_one_target"),
            models.CheckConstraint(condition=(
                Q(source_kind="manual", role_assignment__isnull=True, shift_signup__isnull=True)
                | Q(source_kind="role", role_assignment__isnull=False, shift_signup__isnull=True)
                | Q(source_kind="shift", role_assignment__isnull=True, shift_signup__isnull=False)),
                name="event_entitlement_source_shape"),
            models.UniqueConstraint(fields=["role_assignment"],
                condition=Q(revoked_at__isnull=True, source_kind="role"), name="event_entitlement_live_role"),
            models.UniqueConstraint(fields=["shift_signup"],
                condition=Q(revoked_at__isnull=True, source_kind="shift"), name="event_entitlement_live_shift"),
            models.UniqueConstraint(fields=["grant"], condition=Q(revoked_at__isnull=True,
                source_kind="manual"), name="event_entitlement_live_manual"),
            models.CheckConstraint(condition=(Q(valid_from__isnull=True) | Q(valid_until__isnull=True)
                | Q(valid_until__gt=models.F("valid_from"))), name="event_entitlement_window"),
        ]


class EventSponsor(EventBound):
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL)
    label = models.CharField(max_length=200)
    logo_reference = models.CharField(max_length=300, blank=True)
    page_reference = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=True)


class EventSponsorTrack(EventBound):
    sponsor = models.ForeignKey(EventSponsor, on_delete=models.CASCADE)
    track = models.ForeignKey("events.HackathonTrack", on_delete=models.CASCADE)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["sponsor", "track"], name="event_sponsor_track_unique")]
