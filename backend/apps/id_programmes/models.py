"""Organisation ID programmes (SPEC §4.3), switched by `membership.id_programmes` (#128 C-12).

An internal, separable app with no module key. A programme belongs to an organisation
and is hosted by a space that organisation OWNS. A holder needs no membership of the
host space (Q-I7). Holder name, email, answers and the private reason are scoped PII.
"""
from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin


class IdProgramme(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    class Validity(models.TextChoices):
        NONE = "none", gettext_noop("No expiry")
        FIXED_DATE = "fixed_date", gettext_noop("Until a fixed date")
        DAYS = "days", gettext_noop("A number of days from approval")

    class PhotoMode(models.TextChoices):
        NONE = "none", gettext_noop("No photo")
        OPTIONAL = "optional", "Optional"
        REQUIRED = "required", "Required"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT,
                                     related_name="id_programmes")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="id_programmes")
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    registration_open = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=True)
    id_prefix = models.CharField(max_length=6)
    # Never resets; the year in a number is the approval year (Q9).
    next_sequence = models.PositiveIntegerField(default=1)
    validity_mode = models.CharField(max_length=12, choices=Validity.choices, default=Validity.NONE)
    valid_until = models.DateField(null=True, blank=True)
    validity_days = models.PositiveIntegerField(null=True, blank=True)
    photo_mode = models.CharField(max_length=8, choices=PhotoMode.choices, default=PhotoMode.OPTIONAL)
    form_schema = models.JSONField(default=list, blank=True)
    public_verify = models.BooleanField(default=True)
    email_daily_cap = models.PositiveIntegerField(default=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization_id", "name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "slug"], name="uniq_id_programme_slug"),
            models.CheckConstraint(name="id_programme_open_when_active",
                                   condition=Q(registration_open=False) | Q(status="active")),
            models.CheckConstraint(name="id_programme_validity_fields", condition=(
                Q(validity_mode="none") | Q(validity_mode="fixed_date", valid_until__isnull=False)
                | Q(validity_mode="days", validity_days__gte=1, validity_days__lte=3650))),
        ]

    def __str__(self):
        return self.name


class IdProgrammeCard(ScopedPiiModelMixin, models.Model):
    """The holder and their card in one row (SPEC §4.3)."""
    class Status(models.TextChoices):
        PENDING = "pending", gettext_noop("Waiting for approval")
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", gettext_noop("Not approved")
        REVOKED = "revoked", "Revoked"

    class Source(models.TextChoices):
        FORM = "form", gettext_noop("Join form")
        IMPORT = "import", "Import"
        MANUAL = "manual", gettext_noop("Added by staff")

    programme = models.ForeignKey(IdProgramme, on_delete=models.CASCADE, related_name="cards")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="id_programme_cards")
    name = models.TextField(blank=True, default="")
    email = models.TextField(blank=True, default="")
    # Keyed HMAC of the canonical email, for one-entry-per-person without decryption.
    email_digest = models.CharField(max_length=64, blank=True, default="")
    answers = models.TextField(blank=True, default="")
    photo_object_key = models.CharField(max_length=300, blank=True, default="")
    photo_content_type = models.CharField(max_length=64, blank=True, default="")
    photo_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    photo_consent_at = models.DateTimeField(null=True, blank=True)
    photo_consent_version = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    status_reason = models.TextField(blank=True, default="")
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.FORM)
    # The emailed invite of an imported or staff-added row (#128 C-13): linking needs it.
    invite_digest = models.CharField(max_length=64, blank=True, default="")
    id_number = models.CharField(max_length=32, null=True, blank=True)
    sequence = models.PositiveIntegerField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_emailed_at = models.DateTimeField(null=True, blank=True)
    verify_show_name = models.BooleanField(default=False)
    verify_show_photo = models.BooleanField(default=False)
    verify_consent_at = models.DateTimeField(null=True, blank=True)
    # The holder's choice of attachment for "your card" email: the PDF, or PNG images of each side.
    email_format = models.CharField(max_length=3, choices=(("pdf", "PDF"), ("png", "PNG")), default="pdf")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["programme_id", "created_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["programme", "email_digest"], condition=~Q(email_digest=""),
                                    name="uniq_id_programme_card_email"),
            models.UniqueConstraint(fields=["programme", "id_number"], condition=Q(id_number__isnull=False),
                                    name="uniq_id_programme_card_number"),
            models.UniqueConstraint(fields=["programme", "user"], condition=Q(user__isnull=False),
                                    name="uniq_id_programme_card_user"),
        ]
        indexes = [models.Index(fields=["programme", "status"], name="idprogcard_prog_status_idx")]

    @property
    def is_active(self):
        return self.status == self.Status.APPROVED


class IdProgrammeImport(models.Model):
    """The record of one CSV import run; the file itself is never stored."""
    programme = models.ForeignKey(IdProgramme, on_delete=models.CASCADE, related_name="imports")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    source_sha256 = models.CharField(max_length=64)
    rows_total = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    mapping = models.JSONField(default=dict, blank=True)
