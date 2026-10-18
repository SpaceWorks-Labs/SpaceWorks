"""HTTP v1 contracts. Owner identity always comes from the authorized route."""

from rest_framework import serializers as s
from .public_page_sections import StrictSerializer
from .public_page_contract import Document
from .public_page_projected_serializers import ProjectedSection, ProjectedSections
from .public_page_presentation_serializers import EditorCapabilities, PageLimits, Presentation, RevisionSummary


class VersionInput(StrictSerializer):
    version = s.IntegerField(min_value=0)


class SaveInput(VersionInput):
    document = Document()


class PublishInput(VersionInput):
    draft_revision_id = s.UUIDField()


class HandleInput(VersionInput):
    handle = s.CharField(max_length=30)


class HandleAvailability(s.Serializer):
    handle = s.CharField()
    available = s.BooleanField()


class PageEventQuery(s.Serializer):
    events_page = s.IntegerField(min_value=1, default=1)


class HandleResolution(s.Serializer):
    kind = s.ChoiceField(choices=("member", "makerspace", "organization"))
    handle = s.CharField()
    canonical_url = s.CharField()
    redirected = s.BooleanField()
    content_url = s.CharField()


class Asset(s.Serializer):
    id = s.IntegerField()
    alt_text = s.CharField()
    size_bytes = s.IntegerField()
    preview_url = s.CharField()
    pinned = s.BooleanField()


class AssetUploadInput(VersionInput):
    file = s.FileField()
    alt_text = s.CharField(max_length=200)


class EditorState(s.Serializer):
    kind = s.ChoiceField(choices=("makerspace", "organization"))
    owner_id = s.IntegerField()
    version = s.IntegerField()
    handle = s.CharField(allow_null=True)
    draft_revision_id = s.UUIDField(allow_null=True)
    published_revision_id = s.UUIDField(allow_null=True)
    document = Document()
    assets = Asset(many=True)
    capabilities = EditorCapabilities()
    limits = PageLimits()


class AssetUploadResult(s.Serializer):
    asset = Asset()
    state = EditorState()


class Cover(s.Serializer):
    url = s.CharField()
    alt = s.CharField()


class PublicPageProjection(s.Serializer):
    schema_version = s.IntegerField()
    kind = s.ChoiceField(choices=("makerspace", "organization"))
    canonical_url = s.CharField()
    title = s.CharField()
    description = s.CharField(allow_blank=True)
    publication_token = s.UUIDField()
    cover = Cover(allow_null=True)
    presentation = Presentation()
    sections = ProjectedSections()


class PreviewProjection(PublicPageProjection):
    publication_token = s.UUIDField(allow_null=True)
    draft = s.BooleanField()


class RevisionMetadata(s.Serializer):
    id = s.UUIDField()
    created_at = s.DateTimeField()
    created_by_display = s.CharField(allow_null=True)
    summary = RevisionSummary()


class RevisionList(s.Serializer):
    count = s.IntegerField()
    next = s.CharField(allow_null=True)
    previous = s.CharField(allow_null=True)
    results = RevisionMetadata(many=True)
