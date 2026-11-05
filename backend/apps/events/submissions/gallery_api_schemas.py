"""Gallery response schemas: public output is a small explicit allowlist."""

from rest_framework import serializers

from apps.events.judging.serializers import ClosedSerializer, IdList, ResultEnvelope


class GalleryMemberRead(ClosedSerializer):
    display_name = serializers.CharField()
    profile_url = serializers.CharField()
    photo_url = serializers.CharField(required=False)


class GalleryAssetRead(ClosedSerializer):
    public_id = serializers.UUIDField()
    mime = serializers.CharField()
    bytes = serializers.IntegerField()
    sha256 = serializers.CharField()
    kind = serializers.CharField()
    download_url = serializers.CharField()


class GalleryLinkRead(ClosedSerializer):
    kind = serializers.CharField()
    url = serializers.URLField()


class GalleryEntryRead(ClosedSerializer):
    public_id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    consent_version = serializers.IntegerField()
    files_state = serializers.ChoiceField(choices=("available", "expired", "withdrawn"))
    assets = GalleryAssetRead(many=True)
    links = GalleryLinkRead(many=True)
    members = GalleryMemberRead(many=True)
    content_sha256 = serializers.CharField()
    awards = serializers.ListField(child=serializers.DictField(), required=False,
                                   help_text="Award badges ({prize, rank}); only after results are published (L21b).")
    peoples_choice = serializers.BooleanField(required=False,
                                              help_text="A published People's choice winner (#181); absent before publication.")


class GalleryConsentRead(ClosedSerializer):
    team_id = serializers.IntegerField()
    version = serializers.IntegerField()
    metadata_public = serializers.BooleanField()
    asset_ids = IdList()
    link_ids = IdList()
    publication_state = serializers.ChoiceField(choices=("published", "unpublished", "amendment_required"), required=False)
    state = serializers.CharField(required=False)


class GalleryPublishRead(ResultEnvelope):
    count = serializers.IntegerField(required=False)
    entry_id = serializers.IntegerField(required=False)


class PublicAwardRead(ClosedSerializer):
    prize = serializers.CharField()
    rank = serializers.IntegerField()
    title = serializers.CharField()


class PublicFinalistRead(ClosedSerializer):
    title = serializers.CharField()


class PublicResultsRead(ClosedSerializer):
    event_id = serializers.IntegerField()
    version = serializers.IntegerField(allow_null=True, help_text="Null while only finalists are published.")
    published_at = serializers.DateTimeField(allow_null=True)
    awards = PublicAwardRead(many=True)
    finalists = PublicFinalistRead(many=True, required=False, help_text="L21b: the published finalists block.")
    finalists_published_at = serializers.DateTimeField(allow_null=True, required=False)


class AdminGalleryEntryRead(ClosedSerializer):
    id = serializers.IntegerField()
    snapshot_id = serializers.IntegerField()
    version = serializers.IntegerField()
    title = serializers.CharField()
    hidden = serializers.BooleanField()


class AdminGalleryRead(ClosedSerializer):
    id = serializers.IntegerField(allow_null=True)
    version = serializers.IntegerField()
    result_revision_id = serializers.IntegerField(allow_null=True)
    entries = AdminGalleryEntryRead(many=True)
