"""Platform-level requests to host a makerspace on a managed deployment.

One row is one request. An invitation from an existing makerspace or organization is
the same row in status ``invited`` until the invitee answers it. Rows have no tenant:
they are deployment coordination state, omitted from every tenant export, and only
``apps.hosting_requests.workflow`` writes ``status``.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class HostingRequest(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        PENDING_VERIFICATION = "pending_verification", "Awaiting email confirmation"
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Source(models.TextChoices):
        PUBLIC = "public", "Public form"
        INVITED = "invited", "Invitation"

    class InviterKind(models.TextChoices):
        MAKERSPACE = "makerspace", "Makerspace"
        ORGANIZATION = "organization", "Organization"

    class OrganizationChoice(models.TextChoices):
        OWN = "own", "Create my own organization"
        JOIN = "join", "Join the inviting organization"

    status = models.CharField(max_length=24, choices=Status.choices, db_index=True)
    source = models.CharField(max_length=16, choices=Source.choices)
    inviter_kind = models.CharField(max_length=16, choices=InviterKind.choices, blank=True)
    applicant_name = models.CharField(max_length=200, blank=True)
    applicant_email = models.EmailField(max_length=254, blank=True, db_index=True)
    applicant_phone = models.CharField(max_length=32, blank=True)
    space_name = models.CharField(max_length=200)
    proposed_slug = models.SlugField(max_length=50, blank=True)
    location = models.CharField(max_length=200, blank=True)
    space_website_url = models.URLField(max_length=200, blank=True)
    description = models.TextField(max_length=2000, blank=True)
    organization_choice = models.CharField(
        max_length=8, choices=OrganizationChoice.choices, default=OrganizationChoice.OWN,
    )
    new_organization_name = models.CharField(max_length=200, blank=True)
    inviter_makerspace = models.ForeignKey(
        "makerspaces.Makerspace", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    inviter_organization = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    invite_note = models.CharField(max_length=500, blank=True)
    invite_token_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    access_token_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    verification_expires_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    redacted_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    rejection_reason = models.TextField(max_length=2000, blank=True)
    created_makerspace = models.ForeignKey(
        "makerspaces.Makerspace", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("status", "created_at"), name="hostreq_status_created"),
            models.Index(
                fields=("source", "status", "verification_expires_at"), name="hostreq_verify_sweep",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="rejected") | ~Q(rejection_reason=""),
                name="hostreq_rejected_has_reason",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=("accepted", "rejected")) | Q(decided_at__isnull=False),
                name="hostreq_decided_has_time",
            ),
            models.CheckConstraint(
                condition=~Q(status="withdrawn") | Q(withdrawn_at__isnull=False),
                name="hostreq_withdrawn_has_time",
            ),
            models.CheckConstraint(
                condition=~Q(source="public") | (Q(invite_token_digest__isnull=True) & Q(inviter_kind="")),
                name="hostreq_public_has_no_inviter",
            ),
            models.CheckConstraint(
                condition=~Q(source="invited") | ~Q(inviter_kind=""),
                name="hostreq_invited_has_inviter",
            ),
        ]

    def __str__(self):
        return f"{self.space_name} ({self.get_status_display()})"
