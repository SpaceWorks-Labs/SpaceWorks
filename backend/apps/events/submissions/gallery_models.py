"""One-shot gallery selections, live consent generations and append-only history."""

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.events.judging.models_base import AppendOnly, EventOwned


class GalleryConsent(EventOwned):
    team = models.OneToOneField("events.HackathonTeam", on_delete=models.CASCADE, related_name="gallery_consent")
    snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    metadata_public = models.BooleanField(default=False)
    metadata_generation = models.PositiveIntegerField(default=1)


class GalleryConsentItem(models.Model):
    consent = models.ForeignKey(GalleryConsent, on_delete=models.CASCADE, related_name="items")
    asset = models.ForeignKey("events.SubmissionAsset", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    link = models.ForeignKey("events.SubmissionLink", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    active = models.BooleanField(default=False)
    generation = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(asset__isnull=False, link__isnull=True)
                                   | Q(asset__isnull=True, link__isnull=False), name="ev_gallery_consent_item_subject"),
            models.UniqueConstraint(fields=("consent", "asset"), condition=Q(asset__isnull=False), name="ev_gallery_consent_asset"),
            models.UniqueConstraint(fields=("consent", "link"), condition=Q(link__isnull=False), name="ev_gallery_consent_link"),
        ]


class GalleryConsentRevision(AppendOnly):
    consent = models.ForeignKey(GalleryConsent, on_delete=models.CASCADE, related_name="history")
    revision = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=16)
    scope = models.CharField(max_length=8)
    selection = models.JSONField()  # Declared typed asset_ids/link_ids slots, no private text.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("consent", "revision"), name="ev_gallery_consent_revision")]


class GalleryPublication(EventOwned):
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="gallery_publication")
    published_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    result_revision = models.ForeignKey("events.EventResultRevision", null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="+")


class GalleryEntry(EventOwned):
    publication = models.ForeignKey(GalleryPublication, on_delete=models.CASCADE, related_name="entries")
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    snapshot = models.ForeignKey("events.SubmissionSnapshot", on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=12000)
    metadata_generation = models.PositiveIntegerField()
    selection_revision = models.PositiveIntegerField(default=1)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.ForeignKey("events.JudgingReason", null=True, blank=True,
                                     on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("publication", "snapshot", "selection_revision"),
                                               name="ev_gallery_entry_snapshot")]


class GalleryEntryAsset(AppendOnly):
    entry = models.ForeignKey(GalleryEntry, on_delete=models.CASCADE, related_name="assets")
    asset = models.ForeignKey("events.SubmissionAsset", on_delete=models.PROTECT, related_name="+")
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    consent_generation = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("entry", "asset"), name="ev_gallery_entry_asset")]


class GalleryEntryLink(AppendOnly):
    entry = models.ForeignKey(GalleryEntry, on_delete=models.CASCADE, related_name="links")
    link = models.ForeignKey("events.SubmissionLink", on_delete=models.PROTECT, related_name="+")
    url = models.URLField(max_length=2048)
    kind = models.CharField(max_length=24)
    consent_generation = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("entry", "link"), name="ev_gallery_entry_link")]


class GalleryAmendment(AppendOnly):
    publication = models.ForeignKey(GalleryPublication, on_delete=models.CASCADE, related_name="amendments")
    entry = models.ForeignKey(GalleryEntry, null=True, on_delete=models.PROTECT, related_name="+")
    revision = models.PositiveIntegerField()
    result_revision = models.ForeignKey("events.EventResultRevision", null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="+")
    reason = models.ForeignKey("events.JudgingReason", on_delete=models.PROTECT, related_name="+")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("publication", "revision"), name="ev_gallery_amendment_revision")]
