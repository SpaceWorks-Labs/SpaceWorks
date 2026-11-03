"""Card designs, their append-only revision and approval history, and uploaded artwork.

One engine serves four domains (SPEC §4.1): member cards, ID programmes, event ID
cards and event tickets. A design row is either a space default or an override for
exactly one target (plan, title, programme, event, ticket type, or an organisation's
event library default). Holders only ever render `published_document`.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class CardDesign(models.Model):
    class Domain(models.TextChoices):
        MEMBER_CARDS = "member_cards", "Member cards"
        ID_PROGRAMME = "id_programme", "ID programme cards"
        EVENT_CARD = "event_card", "Event ID cards"
        EVENT_TICKET = "event_ticket", "Event tickets"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Waiting for approval"
        PUBLISHED = "published", "Published"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="card_designs")
    domain = models.CharField(max_length=16, choices=Domain.choices)
    name = models.CharField(max_length=80, blank=True, default="")
    plan = models.ForeignKey("makerspaces.MembershipPlan", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="card_designs")
    title = models.ForeignKey("makerspaces.MembershipTitle", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="card_designs")
    # String references: the core engine loads without the separable apps installed.
    programme = models.ForeignKey("id_programmes.IdProgramme", null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="card_designs")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True,
                                     on_delete=models.CASCADE, related_name="card_designs")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="card_designs")
    ticket_type = models.ForeignKey("events.EventTicketType", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="card_designs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    document = models.JSONField()
    published_document = models.JSONField(null=True, blank=True)
    published_revision = models.PositiveIntegerField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # Compare-and-swap counter: every save must quote the revision it read.
    revision = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "domain", "pk"]
        _untargeted = Q(plan__isnull=True, title__isnull=True, programme__isnull=True,
                        organization__isnull=True, event__isnull=True, ticket_type__isnull=True)
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "domain"], condition=_untargeted,
                                    name="uniq_card_design_space_default"),
            models.UniqueConstraint(fields=["makerspace", "plan"], condition=Q(plan__isnull=False),
                                    name="uniq_card_design_plan"),
            models.UniqueConstraint(fields=["makerspace", "title"], condition=Q(title__isnull=False),
                                    name="uniq_card_design_title"),
            models.UniqueConstraint(fields=["programme"], condition=Q(programme__isnull=False),
                                    name="uniq_card_design_programme"),
            models.UniqueConstraint(fields=["organization", "domain"],
                                    condition=Q(organization__isnull=False, event__isnull=True),
                                    name="uniq_card_design_org_default"),
            models.UniqueConstraint(fields=["event", "domain"],
                                    condition=Q(event__isnull=False, ticket_type__isnull=True),
                                    name="uniq_card_design_event"),
            models.UniqueConstraint(fields=["ticket_type", "domain"], condition=Q(ticket_type__isnull=False),
                                    name="uniq_card_design_ticket_type"),
            models.CheckConstraint(name="card_design_domain_targets", condition=(
                Q(domain="member_cards", programme__isnull=True, organization__isnull=True,
                  event__isnull=True, ticket_type__isnull=True) & ~Q(plan__isnull=False, title__isnull=False)
                | Q(domain="id_programme", programme__isnull=False, plan__isnull=True, title__isnull=True,
                    organization__isnull=True, event__isnull=True, ticket_type__isnull=True)
                | Q(domain__in=["event_card", "event_ticket"], plan__isnull=True, title__isnull=True,
                    programme__isnull=True) & (Q(ticket_type__isnull=True) | Q(event__isnull=False))
            )),
            models.CheckConstraint(name="card_design_published_pair", condition=(
                Q(published_document__isnull=True, published_revision__isnull=True)
                | Q(published_document__isnull=False, published_revision__isnull=False))),
        ]

    def __str__(self):
        return f"{self.domain} design {self.pk}"


class CardDesignRevision(models.Model):
    """Append-only: one row per saved revision, never updated."""
    design = models.ForeignKey(CardDesign, on_delete=models.CASCADE, related_name="revisions")
    revision = models.PositiveIntegerField()
    document = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["design_id", "-revision"]
        constraints = [models.UniqueConstraint(fields=["design", "revision"], name="uniq_card_design_revision")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Card design revisions are append-only.")
        super().save(*args, **kwargs)


class CardDesignApproval(models.Model):
    """One approval request per submitted revision; its decision is set once (#128 C-28)."""
    class Decision(models.TextChoices):
        PENDING = "pending", "Waiting"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    design = models.ForeignKey(CardDesign, on_delete=models.CASCADE, related_name="approvals")
    revision = models.PositiveIntegerField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    decision = models.CharField(max_length=12, choices=Decision.choices, default=Decision.PENDING)
    note = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["design_id", "-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["design"], condition=Q(decision="pending"),
                                    name="uniq_card_design_pending_approval"),
        ]


class CardDesignAsset(models.Model):
    """Uploaded design artwork (backgrounds, watermarks, image layers): private bucket only."""
    class Kind(models.TextChoices):
        BACKGROUND = "background", "Background"
        WATERMARK = "watermark", "Watermark"
        IMAGE = "image", "Image"

    asset_id = models.UUIDField(unique=True)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="card_assets")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    object_key = models.CharField(max_length=300, unique=True)
    content_type = models.CharField(max_length=32)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    width_px = models.PositiveIntegerField(default=0)
    height_px = models.PositiveIntegerField(default=0)
    mean_colour = models.CharField(max_length=7, blank=True, default="")
    ready = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["makerspace_id", "-created_at"]
        indexes = [models.Index(fields=["makerspace", "ready"], name="cardasset_ms_ready_idx")]
