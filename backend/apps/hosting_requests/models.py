"""Platform-level requests to host a makerspace on a managed deployment.

One row is one request. An invitation from an existing makerspace or organization is
the same row in status ``invited`` until the invitee answers it. Rows have no tenant:
they are deployment coordination state, omitted from every tenant export, and only
``apps.hosting_requests.workflow`` writes ``status``.
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q


class HostingRequest(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        PENDING_VERIFICATION = "pending_verification", gettext_noop("Awaiting email confirmation")
        SUBMITTED = "submitted", "Submitted"
        CHANGES_REQUESTED = "changes_requested", gettext_noop("Changes requested")
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    class Source(models.TextChoices):
        PUBLIC = "public", gettext_noop("Public form")
        INVITED = "invited", "Invitation"

    class InviterKind(models.TextChoices):
        MAKERSPACE = "makerspace", "Makerspace"
        ORGANIZATION = "organization", "Organization"

    class OrganizationChoice(models.TextChoices):
        OWN = "own", gettext_noop("Create my own organization")
        JOIN = "join", gettext_noop("Join the inviting organization")

    class RequestedKind(models.TextChoices):
        MAKERSPACE = "makerspace", "Makerspace"
        ORGANIZATION = "organization", gettext_noop("Organization workspace")

    status = models.CharField(max_length=24, choices=Status.choices, db_index=True)
    # Decision 295: what the applicant asks to be set up; the approved space gets this kind.
    requested_kind = models.CharField(
        max_length=16, choices=RequestedKind.choices, default=RequestedKind.MAKERSPACE,
    )
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
    # #185 item 5: the size the applicant expects (members); informs the review only.
    expected_members = models.PositiveIntegerField(null=True, blank=True)
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
    # R2 L2 (X31): the reviewer's open request for changes; cleared on resubmission.
    changes_note = models.TextField(max_length=2000, blank=True)
    changes_requested_at = models.DateTimeField(null=True, blank=True)
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
                condition=~Q(status="changes_requested") | Q(redacted_at__isnull=False) | (
                    ~Q(changes_note="") & Q(changes_requested_at__isnull=False)),
                name="hostreq_changes_have_note",
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


class HostingRequestRevision(models.Model):
    """Append-only review history: each request for changes and each resubmission.

    Platform coordination state like its request: no tenant, omitted from tenant exports,
    and its note is wiped with the request's personal details (#49).
    """

    class Kind(models.TextChoices):
        CHANGES_REQUESTED = "changes_requested", gettext_noop("Changes requested")
        RESUBMITTED = "resubmitted", "Resubmitted"

    request = models.ForeignKey(HostingRequest, on_delete=models.CASCADE, related_name="revisions")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    note = models.TextField(max_length=2000, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
