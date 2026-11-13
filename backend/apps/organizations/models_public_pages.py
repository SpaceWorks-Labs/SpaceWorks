"""Deployment-global editorial content; no tenant or tenant-quota ownership."""

import uuid
from django.conf import settings
from django.db import models


class OrganizationPublicPage(models.Model):
    organization = models.OneToOneField("organizations.Organization", on_delete=models.CASCADE,
                                       related_name="public_page")
    version = models.PositiveIntegerField(default=0)
    draft_revision = models.ForeignKey("organizations.OrganizationPublicPageRevision", null=True,
                                      blank=True, on_delete=models.SET_NULL, related_name="+")
    published_revision = models.ForeignKey("organizations.OrganizationPublicPageRevision", null=True,
                                          blank=True, on_delete=models.SET_NULL, related_name="+")


class OrganizationPublicPageRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(OrganizationPublicPage, on_delete=models.CASCADE, related_name="revisions")
    schema_version = models.PositiveSmallIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    document = models.JSONField()


class OrganizationPublicPageAsset(models.Model):
    page = models.ForeignKey(OrganizationPublicPage, on_delete=models.CASCADE, related_name="assets")
    object_key = models.CharField(max_length=300, unique=True)
    size_bytes = models.PositiveIntegerField()
    alt_text = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class OrganizationPublicPageRevisionAsset(models.Model):
    revision = models.ForeignKey(OrganizationPublicPageRevision, on_delete=models.CASCADE,
                                 related_name="asset_references")
    asset = models.ForeignKey(OrganizationPublicPageAsset, on_delete=models.RESTRICT)
    slot = models.CharField(max_length=80)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("revision", "slot"), name="org_page_asset_slot")]


class OrganizationPublicPageRevisionMember(models.Model):
    revision = models.ForeignKey(OrganizationPublicPageRevision, on_delete=models.CASCADE,
                                 related_name="member_references")
    profile = models.ForeignKey("makerspaces.MemberProfile", null=True, on_delete=models.SET_NULL)
    slot = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("revision", "slot"), name="org_page_member_slot")]


class OrganizationPublicPageStorage(models.Model):
    organization = models.OneToOneField("organizations.Organization", on_delete=models.CASCADE,
                                       related_name="page_storage")
    used_bytes = models.PositiveBigIntegerField(default=0)
