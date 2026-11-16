"""Derived card-photo cut-outs and the bulk photo upload batches (decision 314(c) and its 2026-11-11 addendum).

`CardPhotoCutout` is the eraser job AND its result: one row per holder photo, the cut-out kept as a private
object next to the original (which is never touched). A cut-out is valid only while `source_key` still equals the
card's current photo key; a replaced or removed photo makes it stale and it is purged. Staff ID cards have no
photo of their own, so their cut-out hangs off the member card whose photo they show.

`CardPhotoBatch` / `CardPhotoBatchItem` hold a staff bulk upload while it is reviewed: each file is a private
object under `card-photo-batches/` until the batch is applied (or expires); the card keeps nothing from it but the
normal attached photo.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_noop

from .models_holders import HolderCardMixin, exactly_one_holder, one_per_holder


class CardPhotoCutout(HolderCardMixin):
    class State(models.TextChoices):
        QUEUED = "queued", gettext_noop("Queued")
        RUNNING = "running", gettext_noop("Running")
        DONE = "done", gettext_noop("Ready")
        FAILED = "failed", gettext_noop("Failed")

    state = models.CharField(max_length=8, choices=State.choices, default=State.QUEUED)
    error_code = models.CharField(max_length=32, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    source_key = models.CharField(max_length=300)
    cutout_key = models.CharField(max_length=300, blank=True, default="")
    content_type = models.CharField(max_length=32, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    # "Use cut-out" (True) or "Use original" (False): what the card engine's photo layer shows by default.
    use_cutout = models.BooleanField(default=False)
    provider_scope = models.CharField(max_length=8, blank=True, default="")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    by_holder = models.BooleanField(default=False)
    # Decision 345(b): the eraser-notice version in force when the cut-out was requested.
    notice_version = models.CharField(max_length=16, blank=True, default="")
    consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [exactly_one_holder("card_photo_cutout_one_holder"), *one_per_holder("uniq_photo_cutout")]
        indexes = [models.Index(fields=["state", "updated_at"], name="cutout_state_updated_idx")]


class CardPhotoEraserOptOut(HolderCardMixin):
    """Decision 345(b): this photo's owner opted out of background removal. One row per holder card = opted out (opting
    back in deletes it). The photo is then never sent to the eraser by anyone, and the original prints. A privacy
    choice: it travels with the space and appears in the member's own data export."""
    opted_out_at = models.DateTimeField(auto_now_add=True)
    notice_version = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        constraints = [exactly_one_holder("card_eraser_opt_out_one_holder"), *one_per_holder("uniq_card_eraser_opt_out")]


class CardPhotoBatch(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", gettext_noop("Reviewing")
        APPLYING = "applying", gettext_noop("Applying")
        DONE = "done", gettext_noop("Finished")
        CANCELLED = "cancelled", gettext_noop("Cancelled")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=12)  # member_card | staff_card | event_card
    event_id = models.PositiveBigIntegerField(null=True, blank=True)  # events is separable: a plain reference
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    state = models.CharField(max_length=10, choices=State.choices, default=State.DRAFT)
    remove_backgrounds = models.BooleanField(default=False)
    holders_consented = models.BooleanField(default=False)
    file_count = models.PositiveIntegerField(default=0)
    applied_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["expires_at"], name="photo_batch_expiry_idx")]


class CardPhotoBatchItem(models.Model):
    class Decision(models.TextChoices):
        APPLY = "apply", "Apply"
        REPLACE = "replace", "Replace"
        KEEP = "keep", "Keep"
        SKIP = "skip", "Skip"

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        APPLIED = "applied", "Applied"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    batch = models.ForeignKey(CardPhotoBatch, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveIntegerField()
    filename = models.CharField(max_length=200)
    file_key = models.CharField(max_length=300, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)
    match_kind = models.CharField(max_length=8, blank=True, default="")  # number | email | name | ""
    candidates = models.JSONField(default=list, blank=True)  # holder ids that fit the file name
    holder_id = models.PositiveBigIntegerField(null=True, blank=True)
    has_photo = models.BooleanField(default=False)
    decision = models.CharField(max_length=8, choices=Decision.choices, default=Decision.APPLY)
    state = models.CharField(max_length=8, choices=State.choices, default=State.PENDING)
    error_code = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["batch", "position"], name="uniq_photo_batch_position")]
