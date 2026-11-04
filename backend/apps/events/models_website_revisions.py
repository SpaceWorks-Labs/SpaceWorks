"""Complete immutable website snapshots and durable page-owned session identity."""

import uuid
from django.conf import settings
from django.db import models


class EventSessionIdentity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey("events.EventPage", on_delete=models.CASCADE, related_name="session_identities")


class EventSessionAlias(models.Model):
    page = models.ForeignKey("events.EventPage", on_delete=models.CASCADE, related_name="session_aliases")
    identity = models.ForeignKey(EventSessionIdentity, on_delete=models.CASCADE, related_name="aliases")
    slug = models.SlugField(max_length=80)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("page", "slug"), name="event_session_alias_reserved")]


class EventPageRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey("events.EventPage", on_delete=models.CASCADE, related_name="revisions")
    schema_version = models.PositiveSmallIntegerField(default=1)
    source_anchor_start = models.DateTimeField()
    document = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class EventPageRevisionAsset(models.Model):
    revision = models.ForeignKey(EventPageRevision, on_delete=models.CASCADE, related_name="asset_references")
    asset = models.ForeignKey("events.EventPageAsset", on_delete=models.RESTRICT)
    slot = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("revision", "slot"), name="event_revision_asset_slot")]


class EventPageRevisionMember(models.Model):
    revision = models.ForeignKey(EventPageRevision, on_delete=models.CASCADE, related_name="member_references")
    profile = models.ForeignKey("makerspaces.MemberProfile", null=True, on_delete=models.SET_NULL)
    slot = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("revision", "slot"), name="event_revision_member_slot")]
